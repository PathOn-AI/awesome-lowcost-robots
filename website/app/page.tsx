import Link from "next/link";
import { getAllRobots, getCategories } from "@/lib/robots";

export default function Home() {
  const robots = getAllRobots();
  const categories = getCategories(robots);

  return (
    <div>
      {/* Hero */}
      <section className="py-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-bold tracking-tight mb-6">
            Open Source Robotics Lab
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            A curated collection of open-source tools and resources for building
            and controlling low-cost robots — by{" "}
            <a
              href="https://www.pathon.ai"
              className="text-blue-600 hover:underline"
            >
              Pathon Robotics
            </a>
            .
          </p>
          <div className="flex gap-4 justify-center">
            <Link
              href="/robots"
              className="inline-flex items-center px-6 py-3 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
            >
              Explore Robots
            </Link>
            <a
              href="https://github.com/PathOn-AI/pathon_opensource"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center px-6 py-3 border border-gray-300 rounded-lg font-medium hover:bg-gray-50 transition-colors"
            >
              View on GitHub
            </a>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-gray-200 bg-gray-50 py-12 px-6">
        <div className="max-w-4xl mx-auto grid grid-cols-3 gap-8 text-center">
          <div>
            <div className="text-3xl font-bold">{robots.length}</div>
            <div className="text-sm text-gray-500 mt-1">Robots</div>
          </div>
          <div>
            <div className="text-3xl font-bold">{categories.length}</div>
            <div className="text-sm text-gray-500 mt-1">Categories</div>
          </div>
          <div>
            <div className="text-3xl font-bold">100%</div>
            <div className="text-sm text-gray-500 mt-1">Open Source</div>
          </div>
        </div>
      </section>

      {/* Categories preview */}
      <section className="py-16 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold mb-8 text-center">
            Robot Categories
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {categories.map((cat) => {
              const count = robots.filter((r) => r.category === cat).length;
              return (
                <Link
                  key={cat}
                  href={`/robots?category=${encodeURIComponent(cat)}`}
                  className="block p-4 border border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-center"
                >
                  <div className="font-semibold">{cat}</div>
                  <div className="text-sm text-gray-500 mt-1">
                    {count} {count === 1 ? "robot" : "robots"}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* Tools */}
      <section className="py-16 px-6 border-t border-gray-200">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold mb-8 text-center">Our Tools</h2>
          <div className="border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold mb-2">iPhone Sensor Suite</h3>
            <p className="text-gray-600 mb-4">
              Use iPhone as a full sensor suite (LiDAR, RGB, IMU) for robot
              manipulation and navigation — includes Python SDK, ROS2 driver,
              and calibration.
            </p>
            <a
              href="https://github.com/PathOn-AI/pathon_opensource/tree/main/iphone_sensor_suite"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline text-sm font-medium"
            >
              View documentation
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
