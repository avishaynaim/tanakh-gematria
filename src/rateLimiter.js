/**
 * Rate limiting middleware - IP-based request limiting
 * Limits: 100 requests per IP per hour
 */

// In-memory store for rate limit tracking
// Structure: Map<IP, { count: number, windowStart: number }>
const rateLimitStore = new Map();

// Configuration
const RATE_LIMIT = 100; // requests per window
const WINDOW_MS = 60 * 60 * 1000; // 1 hour in milliseconds
const CLEANUP_INTERVAL_MS = 15 * 60 * 1000; // Cleanup every 15 minutes

/**
 * Gets the client's IP address from the request
 * @param {Object} req - Express request object
 * @returns {string} IP address
 */
function getClientIp(req) {
  // Check for forwarded IP (if behind proxy)
  const forwarded = req.headers['x-forwarded-for'];
  if (forwarded) {
    // x-forwarded-for can be a comma-separated list, take the first one
    return forwarded.split(',')[0].trim();
  }

  // Check for real IP header
  if (req.headers['x-real-ip']) {
    return req.headers['x-real-ip'];
  }

  // Fall back to direct connection IP
  return req.socket.remoteAddress || req.connection.remoteAddress || 'unknown';
}

/**
 * Cleans up expired rate limit entries to prevent memory leaks
 */
function cleanupExpiredEntries() {
  const now = Date.now();
  let cleanedCount = 0;

  for (const [ip, data] of rateLimitStore.entries()) {
    // If the window has expired, remove the entry
    if (now - data.windowStart > WINDOW_MS) {
      rateLimitStore.delete(ip);
      cleanedCount++;
    }
  }

  if (cleanedCount > 0) {
    console.log(`[Rate Limiter] Cleaned up ${cleanedCount} expired entries. Store size: ${rateLimitStore.size}`);
  }
}

/**
 * Rate limiting middleware
 * @param {Object} req - Express request object
 * @param {Object} res - Express response object
 * @param {Function} next - Next middleware function
 */
export function rateLimitMiddleware(req, res, next) {
  const ip = getClientIp(req);
  const now = Date.now();

  // Get or create rate limit data for this IP
  let rateLimitData = rateLimitStore.get(ip);

  if (!rateLimitData) {
    // First request from this IP
    rateLimitData = {
      count: 1,
      windowStart: now,
    };
    rateLimitStore.set(ip, rateLimitData);
  } else {
    // Check if the window has expired
    if (now - rateLimitData.windowStart > WINDOW_MS) {
      // Window expired, reset counter
      rateLimitData.count = 1;
      rateLimitData.windowStart = now;
    } else {
      // Within window, increment counter
      rateLimitData.count++;
    }
  }

  // Calculate remaining requests and reset time
  const remaining = Math.max(0, RATE_LIMIT - rateLimitData.count);
  const resetTime = Math.ceil((rateLimitData.windowStart + WINDOW_MS) / 1000); // Unix timestamp in seconds

  // Add rate limit headers
  res.setHeader('X-RateLimit-Limit', RATE_LIMIT);
  res.setHeader('X-RateLimit-Remaining', remaining);
  res.setHeader('X-RateLimit-Reset', resetTime);

  // Check if rate limit exceeded
  if (rateLimitData.count > RATE_LIMIT) {
    const retryAfter = Math.ceil((rateLimitData.windowStart + WINDOW_MS - now) / 1000); // seconds

    res.setHeader('Retry-After', retryAfter);

    return res.status(429).json({
      success: false,
      error: 'RATE_LIMIT_EXCEEDED',
      message: `Rate limit exceeded. Maximum ${RATE_LIMIT} requests per hour allowed.`,
      limit: RATE_LIMIT,
      remaining: 0,
      resetTime: resetTime,
      retryAfter: retryAfter,
    });
  }

  // Request is within rate limit, proceed
  next();
}

/**
 * Starts the periodic cleanup of expired entries
 * @returns {NodeJS.Timeout} Interval ID (can be cleared with clearInterval)
 */
export function startCleanupSchedule() {
  console.log('[Rate Limiter] Starting periodic cleanup (every 15 minutes)');
  return setInterval(cleanupExpiredEntries, CLEANUP_INTERVAL_MS);
}

/**
 * Manually triggers cleanup (useful for testing)
 */
export function triggerCleanup() {
  cleanupExpiredEntries();
}

/**
 * Gets current rate limit statistics (useful for monitoring)
 * @returns {Object} Statistics about the rate limiter
 */
export function getStats() {
  return {
    totalIPs: rateLimitStore.size,
    limit: RATE_LIMIT,
    windowMs: WINDOW_MS,
  };
}

/**
 * Clears all rate limit data (useful for testing)
 */
export function clearAllRateLimits() {
  rateLimitStore.clear();
  console.log('[Rate Limiter] All rate limit data cleared');
}
