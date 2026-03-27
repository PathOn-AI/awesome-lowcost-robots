import { notFound } from "next/navigation";
import Link from "next/link";
import { getAllSlugs, getRobotBySlug, getSpecLabel } from "@/lib/robots";

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const robot = getRobotBySlug(slug);
  if (!robot) return {};
  return {
    title: `${robot.name} — Pathon Robotics Open Source`,
    description: robot.description,
  };
}

export default async function RobotPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const robot = getRobotBySlug(slug);
  if (!robot) notFound();

  const specEntries = Object.entries(robot.specs);
  const midpoint = Math.ceil(specEntries.length / 2);
  const specsLeft = specEntries.slice(0, midpoint);
  const specsRight = specEntries.slice(midpoint);

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="flex items-center gap-4 mb-10">
        <Link
          href="/robots"
          className="flex items-center justify-center w-10 h-10 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <span className="text-lg">&larr;</span>
        </Link>
        <h1 className="text-2xl font-bold uppercase tracking-widest">
          {robot.name}
        </h1>
        <span className="text-sm text-gray-400 uppercase tracking-wide">
          {robot.category}
        </span>
      </div>

      {/* Hero: image + description */}
      <section className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16 pb-16 border-b border-gray-200">
        <div className="rounded-lg overflow-hidden bg-gray-100">
          <img
            src={robot.image}
            alt={robot.name}
            className="w-full h-full object-cover"
          />
        </div>
        <div className="flex items-start">
          <p className="text-lg text-gray-600 leading-relaxed">
            {robot.description}
          </p>
        </div>
      </section>

      {/* Components */}
      {robot.components.length > 0 && (
        <section className="mb-16 pb-16 border-b border-gray-200">
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400 mb-6">
            Components ({robot.components.length})
          </h2>
          <div className="flex flex-col">
            {robot.components.map((comp, i) => (
              <div
                key={i}
                className={`flex items-center justify-between px-4 py-3 ${
                  i % 2 === 0 ? "bg-gray-50" : "bg-white"
                }`}
              >
                <span className="font-medium text-gray-900">{comp.name}</span>
                <span className="text-sm text-gray-500">{comp.type}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Specifications */}
      {specEntries.length > 0 && (
        <section className="mb-16 pb-16 border-b border-gray-200">
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400 mb-6">
            Specifications
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16">
            <div className="flex flex-col">
              {specsLeft.map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-baseline justify-between py-2 border-b border-gray-100"
                >
                  <span className="text-sm text-gray-400">
                    {getSpecLabel(key)}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {value}
                  </span>
                </div>
              ))}
            </div>
            <div className="flex flex-col">
              {specsRight.map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-baseline justify-between py-2 border-b border-gray-100"
                >
                  <span className="text-sm text-gray-400">
                    {getSpecLabel(key)}
                  </span>
                  <span className="text-sm font-medium text-gray-900">
                    {value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* External link */}
      <div>
        <a
          href={robot.link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-6 py-3 bg-gray-900 text-white rounded-lg font-medium hover:bg-gray-800 transition-colors"
        >
          View project &rarr;
        </a>
      </div>
    </div>
  );
}
