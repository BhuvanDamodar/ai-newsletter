FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package.json and install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the application code
COPY . .

# Build the Next.js application
RUN npm run build

# Expose the standard Next.js port
EXPOSE 3000

# Start the application in production mode
CMD ["npm", "run", "start"]
