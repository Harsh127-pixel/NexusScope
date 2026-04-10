FROM node:18-slim

WORKDIR /app

# Install Quasar CLI
RUN npm install -g @quasar/cli

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 9000

CMD ["quasar", "dev", "-p", "9000"]
