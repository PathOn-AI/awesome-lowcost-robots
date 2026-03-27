import { getAllRobots, getCategories, getPurposes } from "@/lib/robots";
import { RobotGrid } from "./robot-grid";

export const metadata = {
  title: "Robots — Pathon Robotics Open Source",
  description: "A map of open-source and low-cost robots across categories.",
};

export default function RobotsPage() {
  const robots = getAllRobots();
  const categories = getCategories(robots);
  const purposes = getPurposes(robots);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight mb-3">Robots</h1>
        <p className="text-gray-600 text-lg">
          A curated map of open-source and low-cost robots. Click any robot to
          learn more.
        </p>
      </div>
      <RobotGrid robots={robots} categories={categories} purposes={purposes} />
    </div>
  );
}
