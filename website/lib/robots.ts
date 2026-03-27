import fs from "fs";
import path from "path";
import matter from "gray-matter";

export interface Component {
  name: string;
  type: string;
}

export interface Robot {
  slug: string;
  name: string;
  category: string;
  description: string;
  link: string;
  image: string;
  content: string;
  specs: Record<string, string>;
  components: Component[];
  purpose: string[];
}

const robotsDirectory = path.join(process.cwd(), "content/robots");

export function getAllRobots(): Robot[] {
  const files = fs.readdirSync(robotsDirectory);
  const robots = files
    .filter((file) => file.endsWith(".md"))
    .map((file) => {
      const slug = file.replace(/\.md$/, "");
      const fullPath = path.join(robotsDirectory, file);
      const fileContents = fs.readFileSync(fullPath, "utf8");
      const { data, content } = matter(fileContents);
      return {
        slug,
        name: data.name,
        category: data.category,
        description: data.description,
        link: data.link,
        image: data.image,
        content,
        specs: data.specs || {},
        components: data.components || [],
        purpose: data.purpose || [],
      };
    });

  return robots;
}

export function getRobotBySlug(slug: string): Robot | undefined {
  return getAllRobots().find((r) => r.slug === slug);
}

export function getAllSlugs(): string[] {
  return getAllRobots().map((r) => r.slug);
}

export function getCategories(robots: Robot[]): string[] {
  return [...new Set(robots.map((r) => r.category))];
}

export function getPurposes(robots: Robot[]): string[] {
  return [...new Set(robots.flatMap((r) => r.purpose))];
}

const SPEC_LABELS: Record<string, string> = {
  dof: "DOF",
  weight: "Weight",
  payload: "Payload",
  reach: "Reach",
  price: "Price",
  controller: "Controller",
  interfaces: "Interfaces",
  power: "Power",
  repeatability: "Repeatability",
  status: "Status",
};

export function getSpecLabel(key: string): string {
  return SPEC_LABELS[key] || key.charAt(0).toUpperCase() + key.slice(1);
}
