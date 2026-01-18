import express from 'express';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { config } from './config.js';
import { googleMapsClient } from './placesClient.js';
import { processLocation } from './locationService.js';
import { searchPlaces } from './placesSearchService.js';
import { validateQueryParameters } from './validation.js';
import { rateLimitMiddleware, startCleanupSchedule } from './rateLimiter.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const app = express();

// Middleware
app.use(express.json());

// Serve static files from public directory
app.use(express.static(join(__dirname, '..', 'public')));

// Health check endpoint (no rate limiting)
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Main search endpoint with comprehensive validation (primary endpoint)
// Apply rate limiting middleware
app.get('/api/places/search', rateLimitMiddleware, async (req, res) => {
  try {
    // Validate all query parameters
    const validation = validateQueryParameters(req.query);

    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: 'INVALID_PARAMETERS',
        message: validation.errors.join('; '),
        errors: validation.errors,
      });
    }

    const params = validation.params;

    // Process location (handles geocoding if city name provided)
    const location = await processLocation({
      city: params.city,
      latitude: params.latitude,
      longitude: params.longitude,
    });

    // Search for places with validated parameters
    const closedSaturday = req.query.closedSaturday !== 'false';
    const places = await searchPlaces({
      latitude: location.latitude,
      longitude: location.longitude,
      radius: params.radius,
      minRating: params.minRating,
      minReviews: params.minReviews,
      type: params.type,
      closedSaturday: closedSaturday,
    });

    // Return results with metadata
    res.json({
      success: true,
      location: {
        latitude: location.latitude,
        longitude: location.longitude,
        formattedAddress: location.formattedAddress,
      },
      filters: {
        radius: params.radius || config.defaultRadius,
        minRating: params.minRating !== undefined ? params.minRating : config.defaultMinRating,
        minReviews: params.minReviews !== undefined ? params.minReviews : config.defaultMinReviews,
        type: params.type || 'both',
      },
      count: places.length,
      places,
    });
  } catch (error) {
    console.error('API Error:', error.message);

    // Determine error type and status code
    let statusCode = 500;
    let errorCode = 'INTERNAL_ERROR';
    let message = error.message;

    // Validation errors
    if (error.message.includes('must be provided') ||
        error.message.includes('Invalid coordinates') ||
        error.message.includes('Radius must be') ||
        error.message.includes('between')) {
      statusCode = 400;
      errorCode = 'INVALID_PARAMETERS';
    }
    // Location errors (geocoding)
    else if (error.message.includes('City not found')) {
      statusCode = 400;
      errorCode = 'INVALID_LOCATION';
    }
    // Rate limit errors
    else if (error.message.includes('RATE_LIMIT_EXCEEDED')) {
      statusCode = 503;
      errorCode = 'RATE_LIMIT_EXCEEDED';
      message = 'Google API rate limit exceeded. Please try again later.';
    }
    // API errors (including timeout)
    else if (error.message.includes('GOOGLE_API_ERROR') ||
             error.message.includes('timeout') ||
             error.message.includes('API key')) {
      statusCode = 500;
      errorCode = 'GOOGLE_API_ERROR';
    }

    res.status(statusCode).json({
      success: false,
      error: errorCode,
      message,
    });
  }
});

// Legacy endpoint (backward compatibility)
// Apply rate limiting middleware
app.get('/api/places', rateLimitMiddleware, async (req, res) => {
  try {
    // Extract query parameters
    const { city, latitude, longitude, radius, minRating, minReviews } = req.query;

    // Convert numeric parameters
    const lat = latitude ? parseFloat(latitude) : undefined;
    const lng = longitude ? parseFloat(longitude) : undefined;
    const rad = radius ? parseFloat(radius) : undefined;
    const minRat = minRating ? parseFloat(minRating) : undefined;
    const minRev = minReviews ? parseInt(minReviews, 10) : undefined;

    // Process location (handles geocoding if city name provided)
    const location = await processLocation({
      city,
      latitude: lat,
      longitude: lng,
    });

    // Search for places
    const places = await searchPlaces({
      latitude: location.latitude,
      longitude: location.longitude,
      radius: rad,
      minRating: minRat,
      minReviews: minRev,
    });

    // Return results
    res.json({
      success: true,
      location: {
        latitude: location.latitude,
        longitude: location.longitude,
        formattedAddress: location.formattedAddress,
      },
      filters: {
        radius: rad || config.defaultRadius,
        minRating: minRat !== undefined ? minRat : config.defaultMinRating,
        minReviews: minRev !== undefined ? minRev : config.defaultMinReviews,
      },
      count: places.length,
      places,
    });
  } catch (error) {
    console.error('API Error:', error.message);

    // Return appropriate error response
    const statusCode = error.message.includes('must be provided') ||
                      error.message.includes('Invalid coordinates') ||
                      error.message.includes('Radius cannot exceed')
      ? 400
      : 500;

    res.status(statusCode).json({
      success: false,
      error: error.message,
    });
  }
});

// Start server
const server = app.listen(config.port, () => {
  console.log('\n╔════════════════════════════════════════════════════════════════════════════╗');
  console.log('║                        SERVER STARTED                                      ║');
  console.log('╚════════════════════════════════════════════════════════════════════════════╝\n');
  console.log(`🌐 Web Interface: http://localhost:${config.port}`);
  console.log(`🔧 API Endpoint:  http://localhost:${config.port}/api/places/search`);
  console.log(`❤️  Health Check:  http://localhost:${config.port}/health\n`);

  console.log(`Configuration:`);
  console.log(`  - Default radius: ${config.defaultRadius} km`);
  console.log(`  - Max radius: ${config.maxRadius} km`);
  console.log(`  - Default min rating: ${config.defaultMinRating}`);
  console.log(`  - Default min reviews: ${config.defaultMinReviews}`);

  console.log(`\nRate Limiting:`);
  console.log(`  - Limit: 100 requests per hour per IP`);
  console.log(`  - Cleanup interval: every 15 minutes`);

  console.log('\n✅ Ready to accept requests!');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  // Start rate limit cleanup schedule
  startCleanupSchedule();
});

// Increase server timeout to 5 minutes (300 seconds) to handle multiple page requests
// Google API pagination can take time: up to 6 pages * 3 seconds delay = 18+ seconds minimum
server.timeout = 300000; // 5 minutes
server.keepAliveTimeout = 310000; // Slightly longer than timeout
server.headersTimeout = 320000; // Slightly longer than keepAliveTimeout
