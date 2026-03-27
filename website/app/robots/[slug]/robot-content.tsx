"use client";

import ReactMarkdown from "react-markdown";

export function RobotContent({ content }: { content: string }) {
  return <ReactMarkdown>{content}</ReactMarkdown>;
}
