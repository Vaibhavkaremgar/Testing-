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

# Expose port (Railway will set PORT env var)
EXPOSE $PORT

# Use start script with serve
CMD ["npm", "start"]