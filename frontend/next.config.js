/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'standalone', // Enable standalone output for Docker
  experimental: {
    // Required for Docker deployment
    outputFileTracingRoot: undefined,
  },
  // Allow backend domain for images/API
  images: {
    domains: ['localhost', 'backend'],
  },
}

module.exports = nextConfig 