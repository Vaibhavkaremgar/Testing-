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

# Run the production server that redirects /jobs/* before SPA fallback.
CMD ["node", "server.js"]
