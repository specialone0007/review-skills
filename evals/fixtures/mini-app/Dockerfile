FROM node:20-alpine
WORKDIR /app
COPY . .
RUN npm ci --omit=dev
# EXPOSE immediately followed by CMD: the port scan must stop at the end of this line.
EXPOSE 3000
CMD ["node", "src/server.js"]
