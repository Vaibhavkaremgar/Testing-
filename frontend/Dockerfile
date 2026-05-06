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

# Use a static server that respects serve.json SPA rewrites.
CMD ["sh", "-c", "npx serve -s dist -l tcp://0.0.0.0:$PORT --config serve.json"]
