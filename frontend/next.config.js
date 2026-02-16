/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Use environment variable for API URL, fallback to localhost
    const apiUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/api/:path*`,
      },
    ];
  },
  // Increase timeout for API routes
  experimental: {
    proxyTimeout: 120000, // 2 minutes in milliseconds
  },
};

module.exports = nextConfig;
