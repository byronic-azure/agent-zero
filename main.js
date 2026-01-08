#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

// Configuration
const PYTHON_SCRIPT = path.join(__dirname, 'run_ui.py');
const HOST = process.env.HOST || '0.0.0.0';
const PORT = process.env.PORT || '80';

// Build arguments for the Python script
const args = [
  PYTHON_SCRIPT,
  `--host=${HOST}`,
  `--port=${PORT}`,
];

// Add dockerized flag if running in container
if (process.env.DOCKERIZED === 'true') {
  args.push('--dockerized=true');
}

console.log(`Starting Agent Zero on ${HOST}:${PORT}...`);

// Spawn the Python process
const pythonProcess = spawn('python', args, {
  stdio: 'inherit',
  cwd: __dirname,
  env: process.env,
});

// Handle process signals for graceful shutdown
const signals = ['SIGINT', 'SIGTERM', 'SIGQUIT'];
signals.forEach((signal) => {
  process.on(signal, () => {
    console.log(`\nReceived ${signal}, shutting down...`);
    pythonProcess.kill(signal);
  });
});

// Handle Python process exit
pythonProcess.on('exit', (code, signal) => {
  if (signal) {
    console.log(`Python process killed by signal: ${signal}`);
    process.exit(1);
  } else {
    console.log(`Python process exited with code: ${code}`);
    process.exit(code || 0);
  }
});

pythonProcess.on('error', (err) => {
  console.error('Failed to start Python process:', err.message);
  process.exit(1);
});
