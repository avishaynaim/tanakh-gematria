#!/usr/bin/env node

/**
 * Places API Client - CLI tool for searching places closed on Saturday
 */

import http from 'http';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// ANSI color codes for terminal output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
};

// Configuration
const DEFAULT_HOST = 'localhost';
const DEFAULT_PORT = 3000;

/**
 * Gets current GPS location using Termux API
 */
async function getCurrentLocation() {
  try {
    const { stdout } = await execAsync('termux-location -p gps');
    const location = JSON.parse(stdout);

    if (!location.latitude || !location.longitude) {
      throw new Error('Could not get valid GPS coordinates');
    }

    return {
      latitude: location.latitude,
      longitude: location.longitude,
    };
  } catch (error) {
    if (error.message.includes('not found') || error.code === 127) {
      throw new Error('termux-location not found. Install it with: pkg install termux-api');
    }
    throw new Error(`Failed to get current location: ${error.message}`);
  }
}

/**
 * Makes HTTP request to the API
 */
function makeRequest(path, host = DEFAULT_HOST, port = DEFAULT_PORT) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: host,
      port,
      path,
      method: 'GET',
    };

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          resolve({
            statusCode: res.statusCode,
            headers: res.headers,
            data: JSON.parse(data),
          });
        } catch (error) {
          reject(new Error(`Failed to parse response: ${error.message}`));
        }
      });
    });

    req.on('error', (error) => {
      reject(new Error(`Request failed: ${error.message}`));
    });

    req.setTimeout(30000, () => {
      req.destroy();
      reject(new Error('Request timeout after 30 seconds'));
    });

    req.end();
  });
}

/**
 * Parses command line arguments
 */
function parseArgs(args) {
  const params = {
    city: null,
    latitude: null,
    longitude: null,
    radius: null,
    minRating: null,
    minReviews: null,
    type: null,
    format: 'table', // table or json
    host: DEFAULT_HOST,
    port: DEFAULT_PORT,
    useCurrentLocation: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    switch (arg) {
      case '--city':
      case '-c':
        params.city = next;
        i++;
        break;
      case '--lat':
      case '--latitude':
        params.latitude = parseFloat(next);
        i++;
        break;
      case '--lng':
      case '--lon':
      case '--longitude':
        params.longitude = parseFloat(next);
        i++;
        break;
      case '--radius':
      case '-r':
        params.radius = parseFloat(next);
        i++;
        break;
      case '--rating':
        params.minRating = parseFloat(next);
        i++;
        break;
      case '--reviews':
        params.minReviews = parseInt(next, 10);
        i++;
        break;
      case '--type':
      case '-t':
        params.type = next;
        i++;
        break;
      case '--format':
      case '-f':
        params.format = next;
        i++;
        break;
      case '--host':
        params.host = next;
        i++;
        break;
      case '--port':
        params.port = parseInt(next, 10);
        i++;
        break;
      case '--here':
      case '--current':
        params.useCurrentLocation = true;
        break;
      case '--help':
      case '-h':
        showHelp();
        process.exit(0);
        break;
      default:
        if (arg.startsWith('-')) {
          console.error(`${colors.red}Unknown option: ${arg}${colors.reset}`);
          console.error(`Use --help for usage information`);
          process.exit(1);
        }
    }
  }

  return params;
}

/**
 * Builds query string from parameters
 */
function buildQueryString(params) {
  const query = [];

  if (params.city) query.push(`city=${encodeURIComponent(params.city)}`);
  if (params.latitude !== null) query.push(`latitude=${params.latitude}`);
  if (params.longitude !== null) query.push(`longitude=${params.longitude}`);
  if (params.radius !== null) query.push(`radius=${params.radius}`);
  if (params.minRating !== null) query.push(`minRating=${params.minRating}`);
  if (params.minReviews !== null) query.push(`minReviews=${params.minReviews}`);
  if (params.type) query.push(`type=${params.type}`);

  return query.length > 0 ? '?' + query.join('&') : '';
}

/**
 * Displays help message
 */
function showHelp() {
  console.log(`
${colors.bright}מערכת חיפוש מסעדות${colors.reset}
חיפוש מסעדות ובתי קפה סגורים בשבת (מקומות כשרים/חלאל)

${colors.bright}שימוש:${colors.reset}
  node client.js [OPTIONS]

${colors.bright}מיקום (ברירת מחדל: GPS נוכחי):${colors.reset}
  (ללא פרמטרים)             שימוש אוטומטי במיקום GPS (ברירת מחדל)
  --here, --current          שימוש במיקום הנוכחי GPS (Termux בלבד)
  -c, --city <שם>            שם עיר (לדוגמה: "תל אביב")
  --lat <קו רוחב>            קואורדינטת קו רוחב (-90 עד 90)
  --lng <קו אורך>            קואורדינטת קו אורך (-180 עד 180)

${colors.bright}סינון (אופציונלי):${colors.reset}
  -r, --radius <ק"מ>         רדיוס חיפוש בק"מ (1-50, ברירת מחדל: 15)
  --rating <כוכבים>          דירוג מינימלי (1.0-5.0, ברירת מחדל: 3.0)
  --reviews <מספר>           כמות ביקורות מינימלית (>= 1, ברירת מחדל: 20)
  -t, --type <סוג>           סוג מקום: "restaurant" או "cafe" (ברירת מחדל: שניהם)

${colors.bright}פלט (אופציונלי):${colors.reset}
  -f, --format <פורמט>       פורמט פלט: "table" או "json" (ברירת מחדל: table)

${colors.bright}חיבור (אופציונלי):${colors.reset}
  --host <hostname>          שרת API (ברירת מחדל: localhost)
  --port <port>              פורט API (ברירת מחדל: 3000)

${colors.bright}אחר:${colors.reset}
  -h, --help                 הצג הודעת עזרה

${colors.bright}דוגמאות:${colors.reset}
  ${colors.dim}# חיפוש במיקום הנוכחי (אוטומטי)${colors.reset}
  node client.js

  ${colors.dim}# חיפוש בתל אביב${colors.reset}
  node client.js --city "Tel Aviv"

  ${colors.dim}# חיפוש לפי קואורדינטות עם רדיוס מותאם${colors.reset}
  node client.js --lat 32.0853 --lng 34.7818 --radius 10

  ${colors.dim}# מסעדות איכותיות בלבד${colors.reset}
  node client.js --city Jerusalem --rating 4.5 --reviews 100 --type restaurant

  ${colors.dim}# פלט JSON${colors.reset}
  node client.js --city "Tel Aviv" --format json

  ${colors.dim}# שימוש ב-API מרוחק${colors.reset}
  node client.js --city "Tel Aviv" --host api.example.com --port 8080
`);
}

/**
 * Formats distance with units
 */
function formatDistance(km) {
  if (km < 1) {
    return `${Math.round(km * 1000)}m`;
  }
  return `${km.toFixed(2)}km`;
}

/**
 * Formats rating with stars
 */
function formatRating(rating) {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  let stars = '★'.repeat(fullStars);
  if (hasHalfStar) stars += '½';
  return `${stars} ${rating.toFixed(1)}`;
}

/**
 * Displays results in table format
 */
function displayTableFormat(response) {
  const { location, filters, count, places } = response.data;

  console.log(`\n${colors.bright}${colors.cyan}תוצאות חיפוש${colors.reset}`);
  console.log(`${colors.dim}────────────────────────────────────────────────────${colors.reset}`);
  console.log(`${colors.bright}מיקום:${colors.reset} ${location.formattedAddress}`);
  console.log(`${colors.bright}קואורדינטות:${colors.reset} ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`);
  console.log(`${colors.bright}סינון:${colors.reset} רדיוס=${filters.radius}ק"מ, דירוג>=${filters.minRating}, ביקורות>=${filters.minReviews}, סוג=${filters.type}`);
  console.log(`${colors.bright}תוצאות:${colors.reset} ${count} מקומות נמצאו`);

  // Rate limit info
  const rateLimit = {
    limit: response.headers['x-ratelimit-limit'],
    remaining: response.headers['x-ratelimit-remaining'],
    reset: response.headers['x-ratelimit-reset'],
  };

  if (rateLimit.limit) {
    const resetDate = new Date(parseInt(rateLimit.reset) * 1000);
    const remaining = rateLimit.remaining;
    const limitColor = remaining < 20 ? colors.red : remaining < 50 ? colors.yellow : colors.green;

    console.log(`${colors.bright}הגבלת קצב:${colors.reset} ${limitColor}${remaining}${colors.reset}/${rateLimit.limit} בקשות נותרו (מתאפס ${resetDate.toLocaleTimeString()})`);
  }

  console.log(`${colors.dim}────────────────────────────────────────────────────${colors.reset}\n`);

  if (count === 0) {
    console.log(`${colors.yellow}לא נמצאו מקומות התואמים את הקריטריונים.${colors.reset}`);
    console.log(`נסה להתאים את הסינון (רדיוס, דירוג, או ביקורות).`);
    return;
  }

  // Display each place
  places.forEach((place, index) => {
    console.log(`${colors.bright}${colors.green}${index + 1}. ${place.name}${colors.reset}`);
    console.log(`   ${colors.dim}${place.address}${colors.reset}`);
    console.log(`   ${colors.yellow}${formatRating(place.rating)}${colors.reset} (${place.reviewCount} ביקורות) • ${colors.cyan}${formatDistance(place.distance)}${colors.reset} מרחק`);

    if (place.phone) {
      console.log(`   ${colors.blue}📞${colors.reset} ${place.phone}`);
    }

    // Show Saturday hours
    if (place.openingHours && place.openingHours[5]) {
      console.log(`   ${colors.magenta}🗓️ שבת:${colors.reset}  ${place.openingHours[5]}`);
    }

    console.log(`   ${colors.blue}🔗${colors.reset} ${place.googleMapsUrl}`);
    console.log();
  });
}

/**
 * Displays results in JSON format
 */
function displayJsonFormat(response) {
  console.log(JSON.stringify(response.data, null, 2));
}

/**
 * Displays error message
 */
function displayError(error, statusCode, response) {
  console.error(`\n${colors.bright}${colors.red}שגיאה${colors.reset}`);
  console.error(`${colors.dim}────────────────────────────────────────────────────${colors.reset}`);

  if (statusCode) {
    console.error(`${colors.bright}סטטוס:${colors.reset} ${statusCode}`);
  }

  if (response && response.error) {
    console.error(`${colors.bright}קוד:${colors.reset} ${response.error}`);
    console.error(`${colors.bright}הודעה:${colors.reset} ${response.message}`);

    if (response.errors && response.errors.length > 0) {
      console.error(`${colors.bright}פרטים:${colors.reset}`);
      response.errors.forEach(err => {
        console.error(`  • ${err}`);
      });
    }

    // Rate limit specific error
    if (response.error === 'RATE_LIMIT_EXCEEDED' && response.retryAfter) {
      const minutes = Math.ceil(response.retryAfter / 60);
      console.error(`\n${colors.yellow}נסה שוב בעוד ${minutes} דקות.${colors.reset}`);
    }
  } else {
    console.error(`${colors.bright}הודעה:${colors.reset} ${error.message || error}`);
  }

  console.error(`${colors.dim}────────────────────────────────────────────────────${colors.reset}\n`);
}

/**
 * Main function
 */
async function main() {
  const args = process.argv.slice(2);

  // Show help only if explicitly requested
  if (args.length === 1 && (args[0] === '--help' || args[0] === '-h')) {
    showHelp();
    process.exit(0);
  }

  const params = parseArgs(args);

  // Auto-detect: if no location specified, try to use current GPS location
  const hasLocation = params.city || params.useCurrentLocation ||
                     (params.latitude !== null && params.longitude !== null);

  if (!hasLocation) {
    console.log(`${colors.dim}לא צוין מיקום, משתמש במיקום GPS נוכחי...${colors.reset}`);
    params.useCurrentLocation = true;
  }

  // Get current location if requested or auto-detected
  if (params.useCurrentLocation) {
    console.log(`${colors.dim}מקבל מיקום GPS נוכחי...${colors.reset}`);
    try {
      const location = await getCurrentLocation();
      params.latitude = location.latitude;
      params.longitude = location.longitude;
      console.log(`${colors.green}✓${colors.reset} מיקום: ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)}`);
    } catch (error) {
      console.error(`${colors.red}שגיאה: ${error.message}${colors.reset}`);
      console.error(`${colors.yellow}טיפ: אם אין לך גישה ל-GPS, השתמש ב- --city "שם עיר"${colors.reset}`);
      process.exit(1);
    }
  }

  // Validate location parameters
  if (!params.city && (params.latitude === null || params.longitude === null)) {
    console.error(`${colors.red}שגיאה: יש לספק --here, --city, או --lat/--lng${colors.reset}`);
    console.error(`השתמש ב- --help למידע נוסף`);
    process.exit(1);
  }

  // Build query string
  const queryString = buildQueryString(params);
  const path = `/api/places/search${queryString}`;

  console.log(`${colors.dim}מחפש... (${params.host}:${params.port}${path})${colors.reset}`);

  try {
    const response = await makeRequest(path, params.host, params.port);

    if (response.statusCode === 200) {
      if (params.format === 'json') {
        displayJsonFormat(response);
      } else {
        displayTableFormat(response);
      }
      process.exit(0);
    } else {
      displayError(null, response.statusCode, response.data);
      process.exit(1);
    }
  } catch (error) {
    displayError(error);
    console.error(`${colors.yellow}טיפ: וודא שהשרת פועל עם: node src/server.js${colors.reset}\n`);
    process.exit(1);
  }
}

// Run the client
main().catch(error => {
  displayError(error);
  process.exit(1);
});
