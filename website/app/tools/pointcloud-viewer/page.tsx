"use client";

import { useState, ChangeEvent } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { parsePLY, PointCloudData } from "@/lib/plyParser";

const PointCloudViewer = dynamic(
  () => import("@/app/components/PointCloudViewer"),
  { ssr: false }
);

export default function PointCloudViewerPage() {
  const [file, setFile] = useState<File | null>(null);
  const [pointCloudData, setPointCloudData] = useState<PointCloudData | null>(
    null
  );
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState("");

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (!selected) return;

    setFile(selected);
    setParsing(true);
    setError("");
    setPointCloudData(null);

    try {
      const data = await parsePLY(selected);
      setPointCloudData(data);
    } catch (err) {
      setError(
        "Error parsing PLY file: " +
          (err instanceof Error ? err.message : "Unknown error")
      );
    } finally {
      setParsing(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-8 px-6">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm">
        <ol className="flex items-center space-x-2 text-gray-500">
          <li>
            <Link href="/" className="hover:text-green-600">
              Home
            </Link>
          </li>
          <li>/</li>
          <li>
            <Link href="/tools" className="hover:text-green-600">
              Tools
            </Link>
          </li>
          <li>/</li>
          <li className="text-gray-900 font-medium">Point Cloud Viewer</li>
        </ol>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-3 bg-green-100 rounded-lg">
            <svg
              className="h-10 w-10 text-green-600"
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
          </div>
          <div>
            <h1 className="text-4xl font-bold">Point Cloud Viewer</h1>
            <p className="text-gray-600 mt-2">
              Upload a PLY file to visualize point clouds in 3D
            </p>
          </div>
        </div>
      </div>

      {/* Upload */}
      <div className="bg-white shadow-lg rounded-lg p-6 mb-8">
        <div className="space-y-6">
          {/* File input */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Point Cloud File (.ply)
            </label>
            <input
              type="file"
              accept=".ply"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
            />
            {file && (
              <div className="mt-2 text-sm text-gray-600">
                <p>
                  <span className="font-medium">File:</span> {file.name}
                </p>
                <p>
                  <span className="font-medium">Size:</span>{" "}
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </p>
                {parsing && (
                  <p className="text-green-600">Parsing PLY file...</p>
                )}
                {pointCloudData && (
                  <p className="text-green-600">
                    Loaded {pointCloudData.pointCount.toLocaleString()} points
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Info */}
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex gap-3">
              <svg
                className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <div className="text-sm text-green-800">
                <p className="font-medium mb-1">Supported Format:</p>
                <ul className="list-disc list-inside space-y-1 text-green-700">
                  <li>PLY files (ASCII and binary formats)</li>
                  <li>
                    Vertex properties: x, y, z coordinates (required), RGB
                    colors and normals (optional)
                  </li>
                  <li>All processing runs locally in your browser</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-600">{error}</p>
            </div>
          )}
        </div>
      </div>

      {/* 3D Visualization */}
      {pointCloudData && (
        <div className="bg-white shadow-lg rounded-lg p-6">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">
            3D Visualization
          </h2>

          {/* Stats */}
          <div className="mb-4 p-4 bg-green-50 rounded-md">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-sm text-gray-600">Total Points</p>
                <p className="text-2xl font-bold text-gray-900">
                  {pointCloudData.pointCount.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Has Colors</p>
                <p className="text-2xl font-bold text-gray-900">
                  {pointCloudData.colors.some(
                    (v, i) =>
                      i % 3 === 0 &&
                      !(
                        pointCloudData.colors[i] === 0.7 &&
                        pointCloudData.colors[i + 1] === 0.7 &&
                        pointCloudData.colors[i + 2] === 0.7
                      )
                  )
                    ? "Yes"
                    : "No"}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Has Normals</p>
                <p className="text-2xl font-bold text-gray-900">
                  {pointCloudData.normals ? "Yes" : "No"}
                </p>
              </div>
            </div>
          </div>

          {/* Viewer */}
          <div className="border rounded-lg overflow-hidden">
            <PointCloudViewer pointCloud={pointCloudData} />
          </div>
        </div>
      )}
    </div>
  );
}
