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

# Use shell to expand $PORT variable with correct -p flag
CMD ["sh", "-c", "npx serve -s dist -p $PORT"]