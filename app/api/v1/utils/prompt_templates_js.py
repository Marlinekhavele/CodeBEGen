# app/api/utils/prompt_templates_js.py

# JavaScript Endpoint Generation Template
JS_ENDPOINT_GENERATION_TEMPLATE = """
You are an expert JavaScript/Node.js developer helping to create an endpoint for a Backend project.
Generate a JavaScript endpoint based on the following description:
Description: {endpoint_description}
HTTP Method: {method}
Endpoint Path: {endpoint_path}
PROJECT CONTEXT:
{additional_context}

# TASK: CREATE EXPRESS.JS ENDPOINT ONLY
Your task is to generate an Express.js endpoint that implements the described functionality based on the description and context.
Internally identify the main data entity (e.g., 'User', 'Product', 'Order') to ensure correct imports and helper function usage, but DO NOT explicitly state it in the output.

# OUTPUT FORMAT:
Provide ONLY the JavaScript code for the endpoint.

Example Output Structure:
```javascript
const express = require('express');
const router = express.Router();
// ... other imports ...

/**
 * @route GET /example
 * @desc Example endpoint
 */
router.get("/example", async (req, res) => {
  // ... endpoint logic ...
  return res.json({ message: "success" });
});

module.exports = router;
```

# METHOD-CENTRIC RULES
1. **Strict Method Adherence**:
   - Only implement router.{method_lower} methods
   - Use proper Express.js parameter handling for {method}
2. **Response Requirements**:
   - Include appropriate status codes (200 for GET, 201 for POST, etc.)
   - Return structured JSON responses
   - Use proper async/await for asynchronous operations
3. **Import Requirements**:
   - Include only necessary imports based on the endpoint functionality
   - If the endpoint requires database access:
     - Import the model: `const Book = require('../models/book');` (Replace 'book' with the actual entity)
     - Import helpers: `const { getAllBooks, getBookById } = require('../helpers/bookHelpers');` (Replace 'book' with the actual entity)
   - If the endpoint is NOT database-dependent, do NOT import database modules or models.
   - Always include appropriate validation libraries if needed (e.g., express-validator, joi)

4. **Helper Functions**:
   - Assume there are helper functions available in `helpers/[entity]Helpers.js`
   - Use these helper functions in your implementation instead of direct queries when appropriate
   - For database endpoints: use `getAllBooks(req, res)` instead of direct database queries
   - For non-database endpoints: use appropriate utility functions
   - ⚠️ CRITICAL: Every helper function you call in your endpoint code MUST be imported
   - ⚠️ Example: If you call `getBookById(book_id)`, you MUST import it: `const { getBookById } = require('../helpers/bookHelpers');`

# CRITICAL NAMING INSTRUCTION:
# The model names you import (e.g., `const Product = require('../models/product')`)
# and helper function names you call (e.g., `const { getProduct } = require('../helpers/productHelpers')`)
# WILL DICTATE the exact names that *must* be implemented in subsequent generation steps.
# Use clear, conventional names based on the inferred entity (e.g., `Product`, `getProduct`, `createProduct`).

# IMPORT-USAGE CONSISTENCY RULE:
# Before writing any code, identify ALL helper functions you plan to use, then ensure they are ALL imported.
# Common helper function patterns for JavaScript:
# - getAllItems() → const { getAllItems } = require('../helpers/itemHelpers');
# - getItemById() → const { getItemById } = require('../helpers/itemHelpers');
# - createItem() → const { createItem } = require('../helpers/itemHelpers');
# - updateItem() → const { updateItem } = require('../helpers/itemHelpers');
# - deleteItem() → const { deleteItem } = require('../helpers/itemHelpers');
# EVERY function call in your endpoint MUST have a corresponding import statement.

# CODE EXAMPLE
## Database-dependent endpoint:
```javascript
const express = require('express');
const router = express.Router();
const Book = require('../models/book');
// ⚠️ NOTICE: All helper functions used below are imported here
const { getAllBooks, getBookById, createBook } = require('../helpers/bookHelpers');

/**
 * @route GET /books
 * @desc Get all books
 */
router.get('/books', async (req, res) => {
  try {
    // Use helper function instead of direct query
    const books = await getAllBooks();
    return res.status(200).json(books);
  } catch (error) {
    console.error('Error fetching books:', error);
    return res.status(500).json({ message: 'Server error' });
  }
});

/**
 * @route POST /books
 * @desc Create a new book
 */
router.post('/books', async (req, res) => {
  try {
    // Pass request body to the helper function
    const newBook = await createBook(req.body); // createBook is imported above
    if (!newBook) {
      return res.status(400).json({ message: 'Book could not be created' });
    }
    return res.status(201).json(newBook);
  } catch (error) {
    console.error('Error creating book:', error);
    return res.status(500).json({ message: 'Server error' });
  }
});

/**
 * @route GET /books/:id
 * @desc Get a specific book by ID
 */
router.get('/books/:id', async (req, res) => {
  try {
    const book = await getBookById(req.params.id); // getBookById is imported above
    if (!book) {
      return res.status(404).json({ message: 'Book not found' });
    }
    return res.status(200).json(book);
  } catch (error) {
    console.error('Error fetching book:', error);
    return res.status(500).json({ message: 'Server error' });
  }
});
```

## Non-database dependent endpoint:
```javascript
const express = require('express');
const router = express.Router();
const { checkSystemStatus } = require('../helpers/healthHelpers');

/**
 * @route GET /health
 * @desc Check system health status
 */
router.get('/health', async (req, res) => {
  try {
    const statusInfo = await checkSystemStatus();
    return res.status(200).json(statusInfo);
  } catch (error) {
    console.error('Error checking health:', error);
    return res.status(500).json({ message: 'Server error' });
  }
});
```

IMPORTANT:
1. Return ONLY the JavaScript code for the endpoint.
2. Assume models and helper functions for the relevant entity/entities will be generated in other steps or already exist.
3. Do not include any explanations, comments, or text before or after the code block.
4. ALWAYS include the correct imports for any models and helper functions used.
5. ALWAYS use helper functions in your implementation when appropriate, inferring the entity name from the description.
6. Always use async/await for asynchronous operations.
7. Always provide appropriate JSDoc comments for each route.
8. ONLY include database imports for endpoints that need database access based on the description.

# FUNCTION-IMPORT CONSISTENCY CHECK:
Before finalizing your code, verify that EVERY helper function call has a corresponding import.
Examples of CORRECT import patterns:
- If you call getAllBooks() → Must import: const { getAllBooks } = require('../helpers/bookHelpers');
- If you call getBookById() → Must import: const { getBookById } = require('../helpers/bookHelpers');
- If you call createBook() → Must import: const { createBook } = require('../helpers/bookHelpers');

FINAL VERIFICATION: Review all function calls in your endpoint code and ensure corresponding imports exist above. This is the most common source of import errors.
"""

# JavaScript Model Generation Template
JS_MODEL_GENERATION_TEMPLATE = """
You are an expert JavaScript/Node.js developer helping to create a database model.
Generate a Mongoose or Sequelize model for the following entity:
Entity Name: {entity_name}
Entity Description: {entity_description}

CONTEXT PROVIDED (Optional Reference):
The following endpoint code was generated in a previous step.
You can use it for context if helpful, but prioritize the Entity Name and Description for model structure.
Endpoint Code:
```javascript
{endpoint_code}
```

# TASK: CREATE DATABASE MODEL ONLY
Your task is to create a database model for this entity that will work with Express.js applications.
Choose the most appropriate ORM (Mongoose for MongoDB or Sequelize for SQL databases) based on the entity description.

# MODEL REQUIREMENTS
1. **Base Structure**:
   - Create a properly structured model file
   - Include appropriate schema definitions
   - Add timestamps (createdAt, updatedAt)
   - Include proper validation rules

2. **Field Types**:
   - Use appropriate data types for each field
   - Include required, unique, and default constraints as needed
   - Add indexes for fields that will be frequently queried
   - Include appropriate relationships to other models if necessary

3. **Export Requirements**:
   - Properly export the model for use in other files
   - Follow Node.js module patterns

4. **Choose the appropriate ORM**:
   - For document-oriented data: Use Mongoose (MongoDB)
   - For relational data: Use Sequelize (SQL)

# --- ILLUSTRATIVE EXAMPLES ---
Choose the appropriate example based on the data structure needs:

# CODE EXAMPLE FOR MONGOOSE (MongoDB)
```javascript
const mongoose = require('mongoose');
const Schema = mongoose.Schema;

/**
 * User Schema
 * @description Schema for user accounts
 */
const userSchema = new Schema({
  username: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    minlength: 3,
    maxlength: 50,
    index: true
  },
  email: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    lowercase: true,
    match: [/^\\S+@\\S+\\.\\S+$/, 'Please use a valid email address']
  },
  password: {
    type: String,
    required: true,
    minlength: 8
  },
  isActive: {
    type: Boolean,
    default: true
  },
  role: {
    type: String,
    enum: ['user', 'admin', 'guest'],
    default: 'user'
  },
  preferences: {
    type: Map,
    of: String,
    default: {}
  }
}, {
  timestamps: true,
  versionKey: false
});

// Add virtual fields if needed
userSchema.virtual('fullName').get(function() {
  return `${this.firstName} ${this.lastName}`;
});

// Add methods if needed
userSchema.methods.checkPassword = function(password) {
  // Password checking logic would go here
  return true;
};

// Add static methods if needed
userSchema.statics.findByEmail = function(email) {
  return this.findOne({ email });
};

// Middleware (hooks)
userSchema.pre('save', function(next) {
  // Logic before saving
  next();
});

const User = mongoose.model('User', userSchema);

module.exports = User;
```

# CODE EXAMPLE FOR SEQUELIZE (SQL)
```javascript
const { DataTypes, Model } = require('sequelize');
const sequelize = require('../config/database');

/**
 * User Model
 * @description Model for user accounts
 */
class User extends Model {}

User.init({
  id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  username: {
    type: DataTypes.STRING(50),
    allowNull: false,
    unique: true,
    validate: {
      len: [3, 50]
    }
  },
  email: {
    type: DataTypes.STRING,
    allowNull: false,
    unique: true,
    validate: {
      isEmail: true
    }
  },
  password: {
    type: DataTypes.STRING,
    allowNull: false,
    validate: {
      len: [8, 100]
    }
  },
  isActive: {
    type: DataTypes.BOOLEAN,
    defaultValue: true
  },
  role: {
    type: DataTypes.ENUM('user', 'admin', 'guest'),
    defaultValue: 'user'
  }
}, {
  sequelize,
  modelName: 'User',
  tableName: 'users',
  timestamps: true,
  underscored: true // Use snake_case for column names
});

// Define associations in a separate method to avoid circular dependencies
User.associate = (models) => {
  User.hasMany(models.Post, {
    foreignKey: 'userId',
    as: 'posts'
  });

  User.hasOne(models.Profile, {
    foreignKey: 'userId',
    as: 'profile'
  });
};

module.exports = User;
```

IMPORTANT:
1. Return ONLY the JavaScript code for the model for {entity_name}.
2. Choose the most appropriate ORM (Mongoose or Sequelize) based on the entity description.
3. Do not include any explanations, comments, or text after the code.
4. The response should contain ONLY the code itself.
5. ALWAYS include proper validation for fields.
6. If using Mongoose, include appropriate indexes, virtuals, methods, and middleware if needed.
7. If using Sequelize, include appropriate constraints, validations, and association methods if needed.
"""

# JavaScript Schema Generation Template
JS_SCHEMA_GENERATION_TEMPLATE = """
You are an expert JavaScript/Node.js developer helping to create validation schemas for an Express.js application.
Generate validation schemas for the following entity:
Entity Name: {entity_name}

CONTEXT PROVIDED:
Endpoint Code (Defines expected schema usage):
```javascript
{endpoint_code}
```
Model Code (Defines fields/types):
```javascript
{model_code}
```

# TASK: CREATE VALIDATION SCHEMAS ONLY
# 1. Analyze the provided `{endpoint_code}` to understand how validation is being used, if at all.
# 2. Use the provided `{model_code}` as the primary reference for determining the fields and their types within the required schemas.
# 3. Create appropriate validation schemas using either Joi or Express Validator (choose based on what appears to be used in the endpoint code).

# SCHEMA REQUIREMENTS
1. **Schema Framework**:
   - If the endpoint uses Joi: Create Joi validation schemas
   - If the endpoint uses Express Validator: Create express-validator middleware functions
   - If unclear: Default to using Joi for cleaner schema definition

2. **Schema Types**:
   - Create validation for Create operations (POST requests)
   - Create validation for Update operations (PUT/PATCH requests)
   - Create validation for Query parameters if needed (GET requests with filters)

3. **Field Validation**:
   - Include appropriate validation rules for each field
   - Add proper error messages
   - Handle optional vs. required fields appropriately for each operation

# --- ILLUSTRATIVE EXAMPLES ---
Choose the appropriate example based on what's used in the endpoint:

# CODE EXAMPLE FOR JOI
```javascript
const Joi = require('joi');

/**
 * Validation schemas for User entity
 */
const userSchemas = {
  // Schema for creating a new user
  createSchema: Joi.object({
    username: Joi.string().min(3).max(50).required()
      .message({
        'string.min': 'Username must be at least 3 characters',
        'string.max': 'Username cannot exceed 50 characters',
        'any.required': 'Username is required'
      }),
    email: Joi.string().email().required()
      .message({
        'string.email': 'Please provide a valid email address',
        'any.required': 'Email is required'
      }),
    password: Joi.string().min(8).required()
      .message({
        'string.min': 'Password must be at least 8 characters',
        'any.required': 'Password is required'
      }),
    role: Joi.string().valid('user', 'admin', 'guest').default('user')
  }),

  // Schema for updating a user
  updateSchema: Joi.object({
    username: Joi.string().min(3).max(50)
      .message({
        'string.min': 'Username must be at least 3 characters',
        'string.max': 'Username cannot exceed 50 characters'
      }),
    email: Joi.string().email()
      .message({
        'string.email': 'Please provide a valid email address'
      }),
    password: Joi.string().min(8)
      .message({
        'string.min': 'Password must be at least 8 characters'
      }),
    isActive: Joi.boolean(),
    role: Joi.string().valid('user', 'admin', 'guest')
  }),

  // Schema for query parameters
  querySchema: Joi.object({
    role: Joi.string().valid('user', 'admin', 'guest'),
    isActive: Joi.boolean(),
    limit: Joi.number().integer().min(1).max(100).default(10),
    page: Joi.number().integer().min(1).default(1),
    sortBy: Joi.string().valid('username', 'createdAt', 'updatedAt').default('createdAt'),
    sortDir: Joi.string().valid('asc', 'desc').default('desc')
  })
};

module.exports = userSchemas;
```

# CODE EXAMPLE FOR EXPRESS VALIDATOR
```javascript
const { body, query, param, validationResult } = require('express-validator');

/**
 * Validation middleware for User entity
 */
const userValidation = {
  // Validation for creating a new user
  validateCreate: [
    body('username')
      .isString()
      .notEmpty().withMessage('Username is required')
      .isLength({ min: 3, max: 50 }).withMessage('Username must be between 3 and 50 characters'),

    body('email')
      .isEmail().withMessage('Please provide a valid email address')
      .notEmpty().withMessage('Email is required'),

    body('password')
      .isString()
      .notEmpty().withMessage('Password is required')
      .isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),

    body('role')
      .optional()
      .isIn(['user', 'admin', 'guest']).withMessage('Role must be either user, admin, or guest'),

    // Middleware to handle validation errors
    (req, res, next) => {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }
      next();
    }
  ],

  // Validation for updating a user
  validateUpdate: [
    body('username')
      .optional()
      .isString()
      .isLength({ min: 3, max: 50 }).withMessage('Username must be between 3 and 50 characters'),

    body('email')
      .optional()
      .isEmail().withMessage('Please provide a valid email address'),

    body('password')
      .optional()
      .isString()
      .isLength({ min: 8 }).withMessage('Password must be at least 8 characters'),

    body('isActive')
      .optional()
      .isBoolean().withMessage('isActive must be a boolean'),

    body('role')
      .optional()
      .isIn(['user', 'admin', 'guest']).withMessage('Role must be either user, admin, or guest'),

    // Middleware to handle validation errors
    (req, res, next) => {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }
      next();
    }
  ],

  // Validation for query parameters
  validateQuery: [
    query('role')
      .optional()
      .isIn(['user', 'admin', 'guest']).withMessage('Role must be either user, admin, or guest'),

    query('isActive')
      .optional()
      .isBoolean().withMessage('isActive must be a boolean'),

    query('limit')
      .optional()
      .isInt({ min: 1, max: 100 }).withMessage('Limit must be between 1 and 100')
      .toInt(),

    query('page')
      .optional()
      .isInt({ min: 1 }).withMessage('Page must be at least 1')
      .toInt(),

    query('sortBy')
      .optional()
      .isIn(['username', 'createdAt', 'updatedAt']).withMessage('Invalid sort field'),

    query('sortDir')
      .optional()
      .isIn(['asc', 'desc']).withMessage('Sort direction must be asc or desc'),

    // Middleware to handle validation errors
    (req, res, next) => {
      const errors = validationResult(req);
      if (!errors.isEmpty()) {
        return res.status(400).json({ errors: errors.array() });
      }
      next();
    }
  ]
};

module.exports = userValidation;
```

IMPORTANT:
1. Return ONLY the JavaScript code for validation schemas related to {entity_name}.
2. Choose the most appropriate validation library (Joi or express-validator) based on what appears to be used in the endpoint code.
3. Do not include any explanations, comments, or text after the code.
4. The response should contain ONLY the code itself.
5. Ensure all fields from the model have appropriate validation rules.
6. For update operations, fields should typically be optional.
7. Include comprehensive error messages for better user experience.
"""

# JavaScript Migration Generation Template
JS_MIGRATION_GENERATION_TEMPLATE = """
You are an expert JavaScript/Node.js developer helping to create database migrations.
Generate a migration for the following entity:
Entity Name: {entity_name}
Latest Migration ID: {latest_migration_id}

CONTEXT PROVIDED:
Model Code:
```javascript
{model_code}
```

# TASK: CREATE DATABASE MIGRATION ONLY
# Analyze the provided `{model_code}` to determine the required table structure.
# Generate a migration script appropriate for the type of database being used (SQL or MongoDB).

# MIGRATION REQUIREMENTS
1. **Migration Framework**:
   - If the model uses Sequelize, create a Sequelize migration
   - If the model uses Mongoose, create a MongoDB migration using the appropriate library (e.g., migrate-mongo)
   - If unclear, default to Sequelize migration

2. **Structure**:
   - Include up and down functions/methods
   - Handle proper table creation with all fields
   - Include indexes, constraints, and foreign keys as needed
   - Ensure rollback functionality works correctly

3. **Dependency Chain**:
   - This is NOT the first migration
   - Make sure the migration can be applied after the most recent migration
   - Generate a unique identifier for the migration

# --- ILLUSTRATIVE EXAMPLES ---
Choose the appropriate example based on the model:

# CODE EXAMPLE FOR SEQUELIZE MIGRATION
```javascript
'use strict';

/** @type {import('sequelize-cli').Migration} */
module.exports = {
  async up(queryInterface, Sequelize) {
    await queryInterface.createTable('users', {
      id: {
        type: Sequelize.UUID,
        defaultValue: Sequelize.UUIDV4,
        allowNull: false,
        primaryKey: true
      },
      username: {
        type: Sequelize.STRING(50),
        allowNull: false,
        unique: true
      },
      email: {
        type: Sequelize.STRING,
        allowNull: false,
        unique: true
      },
      password: {
        type: Sequelize.STRING,
        allowNull: false
      },
      is_active: {
        type: Sequelize.BOOLEAN,
        defaultValue: true
      },
      role: {
        type: Sequelize.ENUM('user', 'admin', 'guest'),
        defaultValue: 'user'
      },
      created_at: {
        allowNull: false,
        type: Sequelize.DATE
      },
      updated_at: {
        allowNull: false,
        type: Sequelize.DATE
      }
    });

    // Add indexes
    await queryInterface.addIndex('users', ['email']);
    await queryInterface.addIndex('users', ['username']);
  },

  async down(queryInterface, Sequelize) {
    await queryInterface.dropTable('users');
  }
};
```

# CODE EXAMPLE FOR MONGODB MIGRATION (migrate-mongo)
```javascript
module.exports = {
  async up(db, client) {
    // Create collections with validation
    await db.createCollection('users', {
      validator: {
        $jsonSchema: {
          bsonType: 'object',
          required: ['username', 'email', 'password', 'createdAt', 'updatedAt'],
          properties: {
            username: {
              bsonType: 'string',
              minLength: 3,
              maxLength: 50
            },
            email: {
              bsonType: 'string'
            },
            password: {
              bsonType: 'string',
              minLength: 8
            },
            isActive: {
              bsonType: 'bool',
              default: true
            },
            role: {
              enum: ['user', 'admin', 'guest'],
              default: 'user'
            },
            createdAt: {
              bsonType: 'date'
            },
            updatedAt: {
              bsonType: 'date'
            }
          }
        }
      }
    });

    // Create indexes
    await db.collection('users').createIndex({ username: 1 }, { unique: true });
    await db.collection('users').createIndex({ email: a }, { unique: true });
  },

  async down(db, client) {
    await db.collection('users').drop();
  }
};
```

IMPORTANT:
1. Return ONLY the JavaScript code for the migration for {entity_name}.
2. Choose the most appropriate migration format based on the provided model code.
3. Do not include any explanations, comments, or text after the code.
4. The response should contain ONLY the code itself.
5. Include all fields from the model in the migration.
6. For Sequelize migrations, use snake_case for column names if the model specifies underscored: true.
7. For MongoDB migrations, include appropriate validators and indexes.
"""

# JavaScript Helper Functions Generation Template
JS_HELPER_FUNCTIONS_TEMPLATE = """
You are an expert JavaScript/Node.js developer helping to create helper functions for an Express.js application.
Generate helper functions for the following entity:
Entity Name: {entity_name}
Entity Description: {entity_description}

CONTEXT PROVIDED:
Endpoint Code (Defines expected helper function names/calls):
```javascript
{endpoint_code}
```
Model Code (For DB logic):
```javascript
{model_code}
```
Schema Code (For data validation):
```javascript
{schema_code}
```

# TASK: CREATE HELPER FUNCTIONS ONLY
# 1. Analyze the provided `{endpoint_code}` to identify the specific helper function names it imports or calls (e.g., `getAllProducts`, `createProduct`). You **MUST** generate JavaScript code defining *exactly* these helper functions with the signatures implied by the endpoint calls.
# 2. Use the provided `{model_code}` and `{schema_code}` for implementation details.

# HELPER FUNCTION REQUIREMENTS
1. **Function Types**:
   - CRUD operations (create, read, update, delete)
   - Query operations (search, filter, paginate)
   - Business logic operations specific to the entity
   - Utility functions related to the entity

2. **Implementation Requirements**:
   - Use async/await for asynchronous operations
   - Include proper error handling with try/catch
   - Add JSDoc comments for documentation
   - Follow Node.js best practices

3. **Database Interaction**:
   - If using Mongoose: Use appropriate Mongoose methods
   - If using Sequelize: Use appropriate Sequelize methods
   - Handle pagination, sorting, and filtering for list operations

# --- ILLUSTRATIVE EXAMPLE ---
The following example demonstrates helper functions for a User entity:

# CODE EXAMPLE FOR MONGOOSE
```javascript
const User = require('../models/user');

/**
 * User helper functions
 * @description Helper functions for user-related operations
 */
const userHelpers = {
  /**
   * Get all users with optional filtering and pagination
   * @param {Object} options - Query options
   * @param {Object} options.filter - Filter criteria
   * @param {Number} options.limit - Maximum number of results
   * @param {Number} options.page - Page number for pagination
   * @param {String} options.sortBy - Field to sort by
   * @param {String} options.sortDir - Sort direction ('asc' or 'desc')
   * @returns {Promise<Array>} Array of user objects
   */
  getAllUsers: async (options = {}) => {
    try {
      const {
        filter = {},
        limit = 10,
        page = 1,
        sortBy = 'createdAt',
        sortDir = 'desc'
      } = options;

      // Calculate skip value for pagination
      const skip = (page - 1) * limit;

      // Create sort object
      const sort = { [sortBy]: sortDir === 'asc' ? 1 : -1 };

      // Execute query with pagination and sorting
      const users = await User.find(filter)
        .sort(sort)
        .skip(skip)
        .limit(limit)
        .lean();

      // Get total count for pagination
      const total = await User.countDocuments(filter);

      return {
        users,
        pagination: {
          total,
          page,
          limit,
          pages: Math.ceil(total / limit)
        }
      };
    } catch (error) {
      console.error('Error in getAllUsers:', error);
      throw error;
    }
  },

  /**
   * Get user by ID
   * @param {String} userId - User ID
   * @returns {Promise<Object>} User object or null if not found
   */
  getUserById: async (userId) => {
    try {
      const user = await User.findById(userId).lean();
      return user;
    } catch (error) {
      console.error(`Error in getUserById for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Get user by email
   * @param {String} email - User email
   * @returns {Promise<Object>} User object or null if not found
   */
  getUserByEmail: async (email) => {
    try {
      const user = await User.findOne({ email }).lean();
      return user;
    } catch (error) {
      console.error(`Error in getUserByEmail for email ${email}:`, error);
      throw error;
    }
  },

  /**
   * Create a new user
   * @param {Object} userData - User data
   * @returns {Promise<Object>} Created user object
   */
  createUser: async (userData) => {
    try {
      // Check if user with this email already exists
      const existingUser = await userHelpers.getUserByEmail(userData.email);
      if (existingUser) {
        throw new Error('User with this email already exists');
      }

      // Create and save the new user
      const newUser = new User(userData);
      await newUser.save();

      return newUser.toObject();
    } catch (error) {
      console.error('Error in createUser:', error);
      throw error;
    }
  },

  /**
   * Update a user
   * @param {String} userId - User ID
   * @param {Object} updateData - Data to update
   * @returns {Promise<Object>} Updated user object
   */
  updateUser: async (userId, updateData) => {
    try {
      // Find and update the user
      const updatedUser = await User.findByIdAndUpdate(
        userId,
        updateData,
        { new: true, runValidators: true }
      ).lean();

      if (!updatedUser) {
        throw new Error('User not found');
      }

      return updatedUser;
    } catch (error) {
      console.error(`Error in updateUser for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Delete a user
   * @param {String} userId - User ID
   * @returns {Promise<Boolean>} True if deleted, false if not found
   */
  deleteUser: async (userId) => {
    try {
      const result = await User.deleteOne({ _id: userId });
      return result.deletedCount > 0;
    } catch (error) {
      console.error(`Error in deleteUser for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Count users with optional filtering
   * @param {Object} filter - Filter criteria
   * @returns {Promise<Number>} Count of users
   */
  countUsers: async (filter = {}) => {
    try {
      const count = await User.countDocuments(filter);
      return count;
    } catch (error) {
      console.error('Error in countUsers:', error);
      throw error;
    }
  }
};

module.exports = userHelpers;
```

# CODE EXAMPLE FOR SEQUELIZE
```javascript
const { User } = require('../models');
const { Op } = require('sequelize');

/**
 * User helper functions
 * @description Helper functions for user-related operations using Sequelize
 */
const userHelpers = {
  /**
   * Get all users with optional filtering and pagination
   * @param {Object} options - Query options
   * @param {Object} options.filter - Filter criteria
   * @param {Number} options.limit - Maximum number of results
   * @param {Number} options.page - Page number for pagination
   * @param {String} options.sortBy - Field to sort by
   * @param {String} options.sortDir - Sort direction ('asc' or 'desc')
   * @returns {Promise<Array>} Array of user objects
   */
  getAllUsers: async (options = {}) => {
    try {
      const {
        filter = {},
        limit = 10,
        page = 1,
        sortBy = 'createdAt',
        sortDir = 'desc'
      } = options;

      // Calculate offset for pagination
      const offset = (page - 1) * limit;

      // Build query options
      const queryOptions = {
        where: filter,
        limit,
        offset,
        order: [[sortBy, sortDir.toUpperCase()]],
      };

      // Execute query
      const { rows: users, count } = await User.findAndCountAll(queryOptions);

      return {
        users,
        pagination: {
          total: count,
          page,
          limit,
          pages: Math.ceil(count / limit)
        }
      };
    } catch (error) {
      console.error('Error in getAllUsers:', error);
      throw error;
    }
  },

  /**
   * Get user by ID
   * @param {String} userId - User ID
   * @returns {Promise<Object>} User object or null if not found
   */
  getUserById: async (userId) => {
    try {
      const user = await User.findByPk(userId);
      return user ? user.toJSON() : null;
    } catch (error) {
      console.error(`Error in getUserById for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Get user by email
   * @param {String} email - User email
   * @returns {Promise<Object>} User object or null if not found
   */
  getUserByEmail: async (email) => {
    try {
      const user = await User.findOne({ where: { email } });
      return user ? user.toJSON() : null;
    } catch (error) {
      console.error(`Error in getUserByEmail for email ${email}:`, error);
      throw error;
    }
  },

  /**
   * Create a new user
   * @param {Object} userData - User data
   * @returns {Promise<Object>} Created user object
   */
  createUser: async (userData) => {
    try {
      // Check if user with this email already exists
      const existingUser = await userHelpers.getUserByEmail(userData.email);
      if (existingUser) {
        throw new Error('User with this email already exists');
      }

      // Create the new user
      const newUser = await User.create(userData);
      return newUser.toJSON();
    } catch (error) {
      console.error('Error in createUser:', error);
      throw error;
    }
  },

  /**
   * Update a user
   * @param {String} userId - User ID
   * @param {Object} updateData - Data to update
   * @returns {Promise<Object>} Updated user object
   */
  updateUser: async (userId, updateData) => {
    try {
      // Find the user first
      const user = await User.findByPk(userId);

      if (!user) {
        throw new Error('User not found');
      }

      // Update the user
      await user.update(updateData);
      return user.toJSON();
    } catch (error) {
      console.error(`Error in updateUser for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Delete a user
   * @param {String} userId - User ID
   * @returns {Promise<Boolean>} True if deleted, false if not found
   */
  deleteUser: async (userId) => {
    try {
      const result = await User.destroy({ where: { id: userId } });
      return result > 0;
    } catch (error) {
      console.error(`Error in deleteUser for ID ${userId}:`, error);
      throw error;
    }
  },

  /**
   * Count users with optional filtering
   * @param {Object} filter - Filter criteria
   * @returns {Promise<Number>} Count of users
   */
  countUsers: async (filter = {}) => {
    try {
      const count = await User.count({ where: filter });
      return count;
    } catch (error) {
      console.error('Error in countUsers:', error);
      throw error;
    }
  }
};

module.exports = userHelpers;
```

IMPORTANT:
1. Return ONLY the JavaScript code for helper functions related to {entity_name}.
2. Choose the most appropriate database library (Mongoose or Sequelize) based on the model code.
3. Make sure to implement exactly the helper functions that are used in the endpoint code.
4. Include proper error handling with try/catch blocks for all functions.
5. Add JSDoc comments for documentation.
6. For list operations, include pagination, sorting, and filtering support.
7. The response should contain ONLY the code itself.
"""
JS_MODEL_CHANGES_TEMPLATE = """
You are an expert JavaScript developer helping to MODIFY an EXISTING database model.

TASK: ANALYZE REQUIRED CHANGES TO AN EXISTING MODEL
You must identify required changes to an existing JavaScript model (Mongoose or Sequelize) based on the user's request.

Entity Name: {entity_name}
User Request: {prompt_description}

EXISTING MODEL:
```{language}
{existing_model_code}
```

{endpoint_context}

INSTRUCTIONS:
1. Carefully examine the existing model above. This model ALREADY EXISTS in the database.
2. Analyze the user's request to identify what changes are needed.
3. Consider all types of changes: adding new fields, modifying existing fields, removing fields, or renaming fields.

RESPONSE FORMAT:
Return a JSON array of change operations, where each operation has these fields:
- "type": The type of change ("add", "modify", "remove", or "rename")
- "field_name": The name of the field to change
- "definition": For "add" and "modify", the field definition (Mongoose schema type or Sequelize column definition)
- "new_name": For "rename" operations only, the new field name

Example for Mongoose:
[
  {"type": "add", "field_name": "status", "definition": "{ type: String, enum: ['processing', 'shipped', 'delivered'], default: 'processing', required: true }"},
  {"type": "modify", "field_name": "price", "definition": "{ type: Number, required: true }"},
  {"type": "remove", "field_name": "temporary_field"},
  {"type": "rename", "field_name": "customer_name", "new_name": "fullName"}
]

Example for Sequelize:
[
  {"type": "add", "field_name": "status", "definition": "{ type: DataTypes.ENUM('processing', 'shipped', 'delivered'), allowNull: false, defaultValue: 'processing' }"},
  {"type": "modify", "field_name": "price", "definition": "{ type: DataTypes.FLOAT, allowNull: false }"},
  {"type": "remove", "field_name": "temporary_field"},
  {"type": "rename", "field_name": "customer_name", "new_name": "fullName"}
]

If no changes are needed, return an empty array: []

IMPORTANT:
1. Consider the existing model structure carefully.
2. Only suggest changes specifically requested or implied by the user.
3. For renames, include both the old field name and new field name.
4. For modifications, include the complete field definition.
5. Do NOT suggest any changes to standard fields like _id, id, createdAt, updatedAt.
"""

ROUTES_GENERATION_TEMPLATE = """
You are an expert JavaScript/Node.js developer creating Express.js routes.
Generate a route file for the {entity_name} entity described as: {entity_description}.

# CONTROLLER CODE CONTEXT:
```javascript
{endpoint_code}

INSTRUCTIONS:
Create a complete Express.js route file that:
1. Properly imports the controller functions from the controller file
2. Creates appropriate RESTful routes (GET, POST, PUT, DELETE) mapping to controller functions
3. Includes JSDoc comments for each route
4. Follows proper Express.js patterns and ES6 syntax
5. Exports the router

IMPORTANT:
- DO NOT include ANY explanations before or after the code
- Return ONLY the complete JavaScript route file code
- Include ALL necessary imports, middleware, and exports
- Import controller functions using the EXACT same names used in the controller code
- Format the routes based strictly on the controller's implementation
"""
