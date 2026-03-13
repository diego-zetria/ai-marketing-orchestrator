const path = require('path');

const isDev = process.env.NODE_ENV !== 'production';

/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(isDev ? {} : { output: 'export' }),
  images: { unoptimized: true },
  outputFileTracingRoot: path.join(__dirname),
  ...(isDev
    ? {
        rewrites: async () => [
          {
            source: '/api/:path*',
            destination:
              'https://i1z81anpif.execute-api.us-east-1.amazonaws.com/staging/api/:path*',
          },
        ],
      }
    : {}),
};
module.exports = nextConfig;
