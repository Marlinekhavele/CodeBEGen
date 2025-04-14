const express = require('express');
const morgan = require('morgan');
const cors = require('cors');
const helmet = require('helmet');
const xss = require('xss-clean');
const rateLimit = require('express-rate-limit');

module.exports = (app) => {
  // Body parser
  app.use(express.json());

  // Dev logging middleware
  if (process.env.NODE_ENV === 'development') {
    app.use(morgan('dev'));
  }

  // Security middleware
  app.use(helmet()); // Set security headers
  app.use(xss()); // Prevent XSS attacks

  // Rate limiting
  const limiter = rateLimit({
    windowMs: 10 * 60 * 1000, // 10 minutes
    max: 100 // limit each IP to 100 requests per windowMs
  });
  app.use('/api', limiter);

  // Enable CORS
  app.use(cors());

  return app;
};