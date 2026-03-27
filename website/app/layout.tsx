import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Pathon Robotics Open Source",
  description:
    "Open-source tools and resources for building and controlling low-cost robots.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} antialiased`}
    >
      <body className="min-h-screen flex flex-col bg-white text-gray-900">
        <header className="border-b border-gray-200">
          <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
            <Link href="/" className="text-xl font-bold tracking-tight">
              Pathon Robotics <span className="text-gray-400 font-normal">Open Source</span>
            </Link>
            <nav className="flex gap-6 text-sm font-medium">
              <Link href="/" className="hover:text-blue-600 transition-colors">
                Home
              </Link>
              <Link href="/robots" className="hover:text-blue-600 transition-colors">
                Robots
              </Link>
              <a
                href="https://github.com/PathOn-AI/pathon_opensource"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-600 transition-colors"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-t border-gray-200 mt-auto">
          <div className="max-w-6xl mx-auto px-6 py-6 text-sm text-gray-500 text-center">
            Built by{" "}
            <a href="https://www.pathon.ai" className="text-blue-600 hover:underline">
              Pathon Robotics
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
