import type { MDXComponents } from "mdx/types";

export function useMDXComponents(components: MDXComponents): MDXComponents {
  return {
    h1: ({ children }) => (
      <h1 className="text-3xl font-bold mb-4">{children}</h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-2xl font-semibold mb-3 mt-8">{children}</h2>
    ),
    p: ({ children }) => (
      <p className="text-gray-600 mb-4 leading-relaxed">{children}</p>
    ),
    a: ({ children, href }) => (
      <a href={href} className="text-blue-600 hover:underline" target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    ),
    ...components,
  };
}
