# Set Up Inference Server on 3090/4090/5090, make remote api call

## 1. set up the websocket server on 3090/


alternatively, you can set up the remote server



## 2. set up client side code on your macbook pro
python lerobot/inference/websocket_server.py --policy.path=DanqingZ/act_aloha_insertion     --output_dir=outputs/eval/act_aloha_insertion/last     --env.type=aloha     --env.task=AlohaInsertion-v0     --eval.n_episodes=1     --eval.batch_size=1     --policy.device=cuda     --policy.use_amp=false

ngrok http 8765

ValueError: unsupported protocol; expected HTTP/1.1: You have exceeded your limit on connections per minute. This limit will reset within 1 minute. If you expect to continually exceed these limits, please reach out to support (support@ngrok.com)

The above exception was the direct cause of the following exception:

## 3. use the response from remote server instead of direct policy output

python eval_simulation.py     --policy.path=DanqingZ/act_aloha_insertion     --output_dir=outputs/eval/act_aloha_insertion/test_local_server_5 --env.type=aloha     --env.task=AlohaInsertion-v0     --eval.n_episodes=1    --eval.batch_size=1     --policy.device=cuda --policy.use_amp=false