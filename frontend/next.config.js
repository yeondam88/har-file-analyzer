/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone', // Enable standalone output for Docker
  // Allow backend domain for images/API
  images: {
    domains: ['localhost', 'backend'],
  },
  webpack: (config) => {
    // This helps with module resolution in Docker
    config.resolve.fallback = { fs: false, path: false };
    return config;
  },
}

module.exports = nextConfig 