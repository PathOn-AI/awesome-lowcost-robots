import Link from "next/link";

const tools = [
  {
    name: "Point Cloud Viewer",
    description:
      "Upload and visualize PLY point cloud files in 3D directly in your browser. Supports ASCII and binary formats with vertex colors.",
    href: "/tools/pointcloud-viewer",
    icon: (
      <svg
        className="h-8 w-8 text-green-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"
        />
      </svg>
    ),
  },
];

export default function ToolsPage() {
  return (
    <div className="max-w-4xl mx-auto py-16 px-6">
      <div className="text-center mb-12">
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">
          Tools
        </h1>
        <p className="text-base md:text-xl text-gray-600 max-w-2xl mx-auto">
          Browser-based tools for robotics data visualization and analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {tools.map((tool) => (
          <Link
            key={tool.href}
            href={tool.href}
            className="block p-6 border border-gray-200 rounded-lg hover:border-green-300 hover:bg-green-50 transition-colors"
          >
            <div className="flex items-start gap-4">
              <div className="p-2 bg-green-100 rounded-lg flex-shrink-0">
                {tool.icon}
              </div>
              <div>
                <h2 className="text-lg font-semibold mb-1">{tool.name}</h2>
                <p className="text-sm text-gray-600">{tool.description}</p>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
