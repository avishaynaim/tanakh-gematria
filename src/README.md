# Places API - Technical Documentation

## Project Structure

```
/
├── src/
│   ├── config.js              # Configuration and environment variables
│   ├── placesClient.js        # Google Maps client initialization
│   ├── locationService.js     # Location input handling and geocoding
│   ├── placesSearchService.js # Places search and filtering logic
│   ├── validation.js          # Query parameter validation utilities
│   ├── rateLimiter.js         # Rate limiting middleware (100 req/hour per IP)
│   └── server.js              # Express server with API endpoints
├── .env                       # Environment variables (API keys)
├── .env.example               # Environment template
├── package.json               # Dependencies and scripts
└── API.md                     # API endpoint documentation

```

## Location Service

### Overview
The location service handles location input with support for both city names and coordinates, with automatic geocoding for city names.

## Functions

### `processLocation(params)`
Main function to process location input with precedence logic.

**Parameters:**
- `params.city` (string, optional): City name
- `params.latitude` (number, optional): Latitude coordinate
- `params.longitude` (number, optional): Longitude coordinate

**Returns:**
```javascript
{
  latitude: number,
  longitude: number,
  formattedAddress: string
}
```

**Behavior:**
1. If coordinates are provided, uses them (validates range first)
2. If only city name is provided, geocodes it to coordinates
3. If both are provided, coordinates take precedence
4. If neither is provided, throws an error

**Examples:**

```javascript
// Using city name (requires valid Google API key)
const location = await processLocation({ city: 'Tel Aviv' });
// Returns: { latitude: 32.08..., longitude: 34.78..., formattedAddress: "Tel Aviv-Yafo, Israel" }

// Using coordinates
const location = await processLocation({ latitude: 32.0853, longitude: 34.7818 });
// Returns: { latitude: 32.0853, longitude: 34.7818, formattedAddress: "32.0853, 34.7818" }

// Coordinates take precedence
const location = await processLocation({
  city: 'Jerusalem',
  latitude: 32.0853,
  longitude: 34.7818
});
// Returns Tel Aviv coordinates, ignores Jerusalem
```

### `validateCoordinates(latitude, longitude)`
Validates coordinate ranges.

**Returns:** `boolean`

**Valid Ranges:**
- Latitude: -90 to 90
- Longitude: -180 to 180

### `geocodeCity(cityName)`
Converts city name to coordinates using Google Geocoding API.

**Returns:**
```javascript
{
  latitude: number,
  longitude: number,
  formattedAddress: string
}
```

**Throws:** Error if city not found or API call fails

## Location Error Handling

- **Missing location**: "Either city name or coordinates must be provided"
- **Invalid coordinates**: "Invalid coordinates. Latitude must be between -90 and 90, longitude must be between -180 and 180"
- **City not found**: "City not found: {cityName}"
- **Geocoding error**: "Geocoding error: {details}"

---

## Places Search Service

### Overview
Searches for restaurants and cafes using Google Places API and filters for establishments closed on Saturday with quality thresholds.

### Key Functions

#### `searchPlaces(params)`
Main search function that finds and filters places.

**Parameters:**
- `params.latitude` (number, required): Search location latitude
- `params.longitude` (number, required): Search location longitude
- `params.radius` (number, optional): Search radius in km (default: 20, max: 50)
- `params.minRating` (number, optional): Minimum rating (default: 3.0)
- `params.minReviews` (number, optional): Minimum review count (default: 20)

**Returns:** Array of formatted place objects

**Example:**
```javascript
const places = await searchPlaces({
  latitude: 32.0853,
  longitude: 34.7818,
  radius: 20,
  minRating: 3.0,
  minReviews: 20,
});
```

#### `isClosedOnSaturday(openingHours)`
Checks if a place is closed on Saturday.

**Parameters:**
- `openingHours` (object): Opening hours object from Place Details API

**Returns:** `boolean`

**Logic:**
- Checks `weekday_text[6]` (Saturday in Google's format where Sunday=0)
- Looks for "Closed" (case-insensitive) in the Saturday text
- Returns `false` if opening hours data is missing

**Examples:**
```javascript
// Closed on Saturday
isClosedOnSaturday({
  weekday_text: [
    "Sunday: Closed",
    "Monday: 9:00 AM – 5:00 PM",
    "Tuesday: 9:00 AM – 5:00 PM",
    "Wednesday: 9:00 AM – 5:00 PM",
    "Thursday: 9:00 AM – 5:00 PM",
    "Friday: 9:00 AM – 2:00 PM",
    "Saturday: Closed",
  ]
}); // Returns: true

// Open on Saturday
isClosedOnSaturday({
  weekday_text: [
    "Sunday: 9:00 AM – 5:00 PM",
    // ...
    "Saturday: 9:00 AM – 5:00 PM",
  ]
}); // Returns: false
```

#### `calculateDistance(lat1, lng1, lat2, lng2)`
Calculates distance between two coordinates using Haversine formula.

**Parameters:**
- `lat1`, `lng1`: First point coordinates
- `lat2`, `lng2`: Second point coordinates

**Returns:** Distance in kilometers (rounded to 2 decimal places)

**Example:**
```javascript
const distance = calculateDistance(32.0853, 34.7818, 31.7683, 35.2137);
// Returns: 53.89 (Tel Aviv to Jerusalem)
```

#### `formatPlace(place, searchLat, searchLng)`
Formats a place object for API response.

**Returns:**
```javascript
{
  name: string,
  address: string,
  location: { latitude: number, longitude: number },
  rating: number,
  reviewCount: number,
  distance: number,
  openingHours: string[],
  phone: string | null,
  photos: Array<{ reference: string, width: number, height: number }>,
  googleMapsUrl: string,
  placeId: string,
}
```

### Filtering Pipeline

The search applies filters in this order:

1. **Google Places Nearby Search**: Finds restaurants and cafes within radius
2. **Fetch Place Details**: Gets opening hours for each place
3. **Saturday Filter**: Keep only places closed on Saturday
4. **Rating Filter**: Keep only places with rating >= minRating
5. **Review Count Filter**: Keep only places with reviewCount >= minReviews
6. **Distance Calculation**: Add distance field to each result
7. **Sort by Distance**: Order results by proximity (closest first)

### Places Search Error Handling

- **Radius too large**: "Radius cannot exceed 50 km"
- **API errors**: "Places search error: {details}"
- **Missing opening hours**: Places excluded from results (not an error)

### Implementation Notes

- Uses Google Places API Nearby Search for initial search
- Fetches Place Details sequentially for each result to get opening hours
- Places without opening hours data are excluded
- Results limited by Google API pagination (typically 20-60 results)
- Distance calculated using Haversine formula (Earth radius: 6371 km)

---

## Rate Limiting

### Overview
IP-based rate limiting middleware to prevent API abuse while keeping the endpoint publicly accessible.

### Configuration

- **Limit**: 100 requests per hour per IP address
- **Window**: Fixed 1-hour window (3600000 ms)
- **Cleanup**: Every 15 minutes (900000 ms)
- **Storage**: In-memory Map

### Key Functions

#### `rateLimitMiddleware(req, res, next)`
Express middleware that tracks and enforces rate limits.

**Logic:**
1. Extracts client IP from request (supports X-Forwarded-For, X-Real-IP)
2. Gets or creates rate limit entry for IP
3. Checks if window expired (resets counter if expired)
4. Increments request counter
5. Adds rate limit headers to response
6. Returns 429 if limit exceeded, otherwise calls next()

**Headers Added:**
- `X-RateLimit-Limit`: Maximum requests per window (100)
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when rate limit resets
- `Retry-After`: Seconds until reset (only when 429)

**Example:**
```javascript
app.get('/api/places/search', rateLimitMiddleware, async (req, res) => {
  // Your endpoint logic
});
```

#### `startCleanupSchedule()`
Starts periodic cleanup of expired rate limit entries.

**Returns:** Interval ID (can be cleared with clearInterval)

**Purpose:** Prevents memory leaks by removing expired entries every 15 minutes

#### `getClientIp(req)`
Extracts client IP address from request.

**Priority:**
1. X-Forwarded-For header (if behind proxy)
2. X-Real-IP header
3. Socket remote address

#### `cleanupExpiredEntries()`
Removes rate limit entries with expired windows.

**Called:** Automatically every 15 minutes, or manually via `triggerCleanup()`

#### `getStats()`
Returns current rate limiter statistics.

**Returns:**
```javascript
{
  totalIPs: number,    // Number of IPs being tracked
  limit: number,       // Rate limit (100)
  windowMs: number,    // Window duration in ms (3600000)
}
```

#### `clearAllRateLimits()`
Clears all rate limit data (useful for testing).

### Rate Limit Response (429)

```json
{
  "success": false,
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Maximum 100 requests per hour allowed.",
  "limit": 100,
  "remaining": 0,
  "resetTime": 1705334400,
  "retryAfter": 3420
}
```

### Implementation Details

**Storage:**
- In-memory Map with IP as key
- Structure: `Map<IP, { count: number, windowStart: number }>`
- Resets on server restart

**Window Management:**
- Fixed 1-hour windows (not sliding)
- Window starts on first request from IP
- Resets after 1 hour or on cleanup

**Cleanup:**
- Runs every 15 minutes
- Removes entries where `now - windowStart > windowMs`
- Logs cleanup statistics to console

**Exemptions:**
- Health endpoint (`/health`) not rate limited
- Can add more exemptions by conditionally applying middleware

### Testing

**Unit Tests:**
```javascript
import { getStats, clearAllRateLimits, triggerCleanup } from './rateLimiter.js';

// Check initial state
const stats = getStats();

// Clear all limits
clearAllRateLimits();

// Manual cleanup
triggerCleanup();
```

**Integration Tests:**
- Make 50 requests: all should succeed
- Make 101 requests: 101st should return 429
- Check rate limit headers on each response
- Verify cleanup removes expired entries

### Scaling Considerations

**Current Implementation:**
- In-memory storage: suitable for single-instance deployment
- Resets on server restart

**Future Enhancements for Multi-Instance:**
- Redis-based rate limiting for distributed tracking
- Shared storage across multiple server instances
- More sophisticated algorithms (sliding window, token bucket)

**Why In-Memory:**
- Simplicity: no external dependencies
- Performance: very fast lookups
- Sufficient for current use case (single instance)

### Security Notes

- IP can be spoofed if not behind trusted proxy
- X-Forwarded-For header trusted by default
- Consider additional authentication for production at scale
- Rate limits per IP, not per user (public endpoint)
