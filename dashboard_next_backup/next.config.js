/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  turbopack: {
    // Keep Turbopack scoped to this Next.js project directory.
    root: __dirname,
  },

  // Allow the dashboard to call the FastAPI backend running on the mini PC.
  // Configure NEXT_PUBLIC_API_URL in .env.local to point to the backend host.
  // Example: NEXT_PUBLIC_API_URL=http://192.168.1.50:8000
};

module.exports = nextConfig;
