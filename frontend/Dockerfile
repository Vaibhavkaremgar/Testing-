FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Build the app
RUN npm run build

# Use serve's built-in SPA fallback for deep links like /jobs/:slug.
CMD ["sh", "-c", "npx serve -s dist -l tcp://0.0.0.0:$PORT"]
