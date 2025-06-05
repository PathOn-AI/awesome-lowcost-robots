import time
import logging
import asyncio

import torch
import cv2
import numpy as np
import os

from lerobot.common.policies.act.modeling_act import ACTPolicy
from lerobot.common.robot_devices.utils import busy_wait
from lerobot.common.robot_devices.robots.utils import make_robot
from lerobot_client import LeRobotClient
from datetime import datetime


# Rate limiting configurations
CONSERVATIVE_CONFIG = {
    'strategy': 'exponential_backoff',
    'initial_delay': 0.01,  # 500ms base delay - very conservative for ngrok
    'max_delay': 60.0,     # Allow up to 1 minute delays
    'backoff_factor': 2.0,
    'max_retries': 15      # Even more retries for rate limits
}

AGGRESSIVE_CONFIG = {
    'strategy': 'exponential_backoff',
    'initial_delay': 0.15,  # 150ms base delay
    'max_delay': 30.0,      # Up to 30 second delays
    'backoff_factor': 1.5,
    'max_retries': 8
}

SIMPLE_CONFIG = {
    'strategy': 'simple_delay',
    'initial_delay': 0.4,  # Fixed 400ms delay - more conservative for ngrok
}

# Default configuration for ngrok free tier
DEFAULT_RATE_LIMIT_CONFIG = CONSERVATIVE_CONFIG


class AsyncRateLimitHandler:
    """Handles rate limiting with exponential backoff and retry logic for async operations."""
    
    def __init__(self, 
                 initial_delay: float = 0.1, 
                 max_delay: float = 60.0,  # Increased max delay
                 backoff_factor: float = 2.0, 
                 max_retries: int = 10):  # Increased max retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.max_retries = max_retries
        
    async def execute_with_backoff(self, func, *args, **kwargs):
        """Execute async function with exponential backoff on rate limit errors."""
        delay = self.initial_delay
        
        for attempt in range(self.max_retries):
            try:
                # Always add a small delay before each request
                if attempt == 0:
                    await asyncio.sleep(self.initial_delay)
                return await func(*args, **kwargs)
            except Exception as e:
                # Use the enhanced rate limit detection
                if is_rate_limit_error(e):
                    if attempt == self.max_retries - 1:
                        logging.error(f"Max retries ({self.max_retries}) exceeded for rate limiting")
                        # Instead of raising, wait for full reset and try once more
                        logging.info("Waiting 60 seconds for rate limit to fully reset...")
                        await asyncio.sleep(60)
                        try:
                            return await func(*args, **kwargs)
                        except Exception as final_e:
                            logging.error(f"Final attempt failed: {final_e}")
                            raise e
                    
                    # Determine the type of rate limit error for better logging
                    error_str = str(e).lower()
                    if "connectionrefused" in error_str or "websockets.exceptions" in error_str:
                        logging.warning(f"Websocket-based rate limit hit (attempt {attempt + 1}/{self.max_retries}), waiting {delay:.2f}s before retry")
                    else:
                        logging.warning(f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}), waiting {delay:.2f}s before retry")
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * self.backoff_factor, self.max_delay)
                else:
                    # Not a rate limit error, re-raise immediately
                    logging.error(f"Non-rate-limit error: {e}")
                    raise e
        
        raise Exception("Max retries exceeded")


def is_rate_limit_error(exception) -> bool:
    """Enhanced rate limit error detection that looks at the full exception chain."""
    # Convert the entire exception chain to string
    error_chain = str(exception).lower()
    
    # Also check the type and any nested exceptions
    if hasattr(exception, '__cause__') and exception.__cause__:
        error_chain += " " + str(exception.__cause__).lower()
    if hasattr(exception, '__context__') and exception.__context__:
        error_chain += " " + str(exception.__context__).lower()
    
    # Look for rate limit indicators in the full error chain
    rate_limit_indicators = [
        'rate limit', 'exceeded', 'connections per minute', 
        'limit will reset', 'too many requests', 'too many connections',
        'connection limit', 'quota exceeded', 'throttle', 'throttled',
        'unsupported protocol; expected http/1.1: you have exceeded your limit'
    ]
    
    # Special case: websockets library errors during rate limiting
    websocket_rate_limit_indicators = [
        "connectionrefused",
        "module 'websockets.exceptions' has no attribute 'connectionrefused'",
        "invalidmessage",
        "did not receive a valid http response"
    ]
    
    # Check for standard rate limit messages
    is_standard_rate_limit = any(indicator in error_chain for indicator in rate_limit_indicators)
    
    # Check for websocket library errors that occur during rate limiting
    is_websocket_rate_limit = any(indicator in error_chain for indicator in websocket_rate_limit_indicators)
    
    return is_standard_rate_limit or is_websocket_rate_limit


async def run_inference():
    """Main async inference function."""
    # Configuration
    inference_time_s = 30
    fps = 25
    device = "mps" 

    # Initialize rate limiting handler
    rate_limit_config = DEFAULT_RATE_LIMIT_CONFIG.copy()
    rate_handler = AsyncRateLimitHandler(
        initial_delay=rate_limit_config.get('initial_delay', 0.01),
        max_delay=rate_limit_config.get('max_delay', 60.0),
        backoff_factor=rate_limit_config.get('backoff_factor', 2.0),
        max_retries=rate_limit_config.get('max_retries', 15)
    )

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Using rate limiting strategy: {rate_limit_config['strategy']} with config: {rate_limit_config}")

    # Initialize policy and robot
    policy = ACTPolicy.from_pretrained("DanqingZ/act_so100_filtered_yellow_cuboid")
    policy.to(device)

    robot = make_robot("so100")
    robot.connect()
    output_dir = "/Users/danqingzhang/Desktop/learning/awesome-lerobot/inference/act_soarm100/images/"
    os.makedirs(output_dir, exist_ok=True)

    # Performance tracking variables
    iteration_times = []
    running_total_time = 0.0
    successful_steps = 0
    start_overall = time.perf_counter()

    # Use async context manager for LeRobotClient
    async with LeRobotClient("ws://localhost:8766") as client:
        logging.info("✅ LeRobot client connected and ready")
        
        try:
            # Main inference loop
            for step in range(inference_time_s * fps):
                print('Iteration Start Time:', datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S.%f")[:-3])
                start_time = time.perf_counter()
                observation = robot.capture_observation()
                
                # Save images
                image = observation['observation.images.phone']
                np_image = np.array(image)
                np_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(os.path.join(output_dir, f"image_phone_{step}.jpg"), np_image)
                
                image = observation['observation.images.on_robot']
                np_image = np.array(image)
                np_image = cv2.cvtColor(np_image, cv2.COLOR_RGB2BGR)
                cv2.imwrite(os.path.join(output_dir, f"image_on_robot_{step}.jpg"), np_image)
                
                print(f"Step {step}")
                
                # Process observation
                for name in observation:
                    observation[name] = observation[name].numpy()
                    print(name, observation[name].shape)

                # Get action with rate limiting (using async client)
                async def get_action():
                    return await client.select_action(observation)
                
                print('Done processing observation:', datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S.%f")[:-3])
                try:
                    action = await rate_handler.execute_with_backoff(get_action)
                    print('Get Action Time:', datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S.%f")[:-3])
                    action = torch.from_numpy(action)
                    action = action.squeeze(0)
                    print('Action Conversion Time:', datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S.%f")[:-3])
                    robot.send_action(action)
                    print('Robot Send Action Time:', datetime.now().strftime("%A, %B %d, %Y at %H:%M:%S.%f")[:-3])
                    
                    # Calculate iteration performance
                    iteration_time = time.perf_counter() - start_time
                    iteration_ms = iteration_time * 1000
                    
                    # Update running averages
                    successful_steps += 1
                    running_total_time += iteration_time
                    iteration_times.append(iteration_time)
                    
                    # Calculate running averages
                    running_avg_ms = (running_total_time / successful_steps) * 1000
                    running_avg_fps = 1.0 / (running_total_time / successful_steps)
                    
                    # Calculate overall performance since start
                    elapsed_overall = time.perf_counter() - start_overall
                    overall_fps = successful_steps / elapsed_overall
                    
                    # Print performance stats
                    print(f"📊 Step {step}: {iteration_ms:.1f}ms | "
                          f"Avg: {running_avg_ms:.1f}ms ({running_avg_fps:.1f} FPS) | "
                          f"Overall: {overall_fps:.1f} FPS | "
                          f"Success: {successful_steps}/{step+1}")
                    
                except Exception as e:
                    logging.error(f"Failed to get action at step {step}: {e}")
                    # Print failure stats
                    elapsed_overall = time.perf_counter() - start_overall
                    overall_fps = successful_steps / elapsed_overall if successful_steps > 0 else 0
                    print(f"❌ Step {step}: FAILED | "
                          f"Overall: {overall_fps:.1f} FPS | "
                          f"Success: {successful_steps}/{step+1}")
                    continue

                dt_s = time.perf_counter() - start_time
                busy_wait(1 / fps - dt_s)

        finally:
            # Print final performance summary
            total_elapsed = time.perf_counter() - start_overall
            
            print("\n" + "="*60)
            print("📈 FINAL PERFORMANCE SUMMARY")
            print("="*60)
            
            if successful_steps > 0:
                final_avg_ms = (running_total_time / successful_steps) * 1000
                final_avg_fps = 1.0 / (running_total_time / successful_steps)
                overall_fps = successful_steps / total_elapsed
                success_rate = (successful_steps / (inference_time_s * fps)) * 100
                
                print(f"Total steps attempted: {inference_time_s * fps}")
                print(f"Successful steps: {successful_steps}")
                print(f"Success rate: {success_rate:.1f}%")
                print(f"Average iteration time: {final_avg_ms:.1f}ms")
                print(f"Average processing FPS: {final_avg_fps:.1f}")
                print(f"Overall throughput FPS: {overall_fps:.1f}")
                print(f"Total runtime: {total_elapsed:.1f}s")
                
                # Additional stats if you want them
                if len(iteration_times) > 1:
                    import statistics
                    median_ms = statistics.median(iteration_times) * 1000
                    print(f"Median iteration time: {median_ms:.1f}ms")
            else:
                print("❌ No successful iterations completed")
            
            print("="*60)
            
            # Robot cleanup (client cleanup handled by context manager)
            try:
                robot.disconnect()
                logging.info("✅ Robot disconnected")
            except Exception as e:
                logging.warning(f"Error during robot cleanup: {e}")


def main():
    """Entry point that runs the async inference."""
    try:
        asyncio.run(run_inference())
    except KeyboardInterrupt:
        logging.info("Inference interrupted by user")
    except Exception as e:
        logging.error(f"Inference failed: {e}")
        raise


if __name__ == "__main__":
    main()