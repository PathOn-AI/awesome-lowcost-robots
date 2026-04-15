"use client";

import { useState } from "react";
import Link from "next/link";
import { HiMenu, HiX } from "react-icons/hi";
import { FaGithub, FaLinkedin, FaTwitter, FaDiscord } from "react-icons/fa";

export function MobileMenu() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <>
      {/* Mobile Menu Button */}
      <div className="md:hidden">
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="text-gray-700"
        >
          {mobileMenuOpen ? (
            <HiX className="h-7 w-7" />
          ) : (
            <HiMenu className="h-7 w-7" />
          )}
        </button>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden absolute top-full left-0 right-0 bg-white border-t border-gray-200 shadow-sm z-50">
          <div className="px-6 py-6 space-y-4">
            <Link
              href="/"
              className="block text-lg font-semibold text-gray-700 hover:text-green-600"
              onClick={() => setMobileMenuOpen(false)}
            >
              Home
            </Link>
            <Link
              href="/robots"
              className="block text-lg font-semibold text-gray-700 hover:text-green-600"
              onClick={() => setMobileMenuOpen(false)}
            >
              Robots
            </Link>
            <Link
              href="/tools"
              className="block text-lg font-semibold text-gray-700 hover:text-green-600"
              onClick={() => setMobileMenuOpen(false)}
            >
              Tools
            </Link>
            {/* Social Icons */}
            <div className="flex items-center gap-5 pt-2">
              <a href="https://github.com/PathOn-AI" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-green-600" aria-label="GitHub"><FaGithub className="h-5 w-5" /></a>
              <a href="https://www.linkedin.com/company/path-on/" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-green-600" aria-label="LinkedIn"><FaLinkedin className="h-5 w-5" /></a>
              <a href="https://x.com/pathonai" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-green-600" aria-label="Twitter"><FaTwitter className="h-5 w-5" /></a>
              <a href="https://discord.gg/xukJ3nh9wC" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-green-600" aria-label="Discord"><FaDiscord className="h-5 w-5" /></a>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
