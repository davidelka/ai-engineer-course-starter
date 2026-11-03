# Node.js backend cheat sheet

- Express error handling: an error middleware has four arguments (err, req, res, next) and goes last.
- Async route handlers: wrap them, or use Express 5, which forwards rejected promises to the error middleware.
- Graceful shutdown: on SIGTERM stop accepting connections, finish in-flight requests, close the DB pool.
- pm2: `pm2 start app.js -i max` runs one process per CPU core; `pm2 logs` tails the logs.
- Never log request bodies with personal data; redact before logging.
