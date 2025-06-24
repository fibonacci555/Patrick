const fs = require('fs-extra');
const path = require('path');
const csv = require('csv-parse/sync');

// Configs directory
const CONFIG_DIR = path.join(__dirname, 'configs');
fs.ensureDirSync(CONFIG_DIR);

// Chat ID (hardcoded for now, can be passed via command line or config)
const CHAT_ID = 5078730107; // Replace with your desired chat ID

// Read CSV file
const csvPath = path.join(__dirname, 'generate.csv');
const csvContent = fs.readFileSync(csvPath, 'utf-8');
const records = csv.parse(csvContent, {
  columns: true,
  skip_empty_lines: true,
  trim: true,
});

// Group deals by brand
const brandDeals = {};
for (const record of records) {
  const brand = record['Brend'];
  const slug = record['Link'].split('/').pop(); // Extract slug from URL (e.g., 'ofp-funding')
  const baseUrl = 'https://www.wethrift.com/api/submit-action'; // Consistent base URL
  if (!brandDeals[brand]) {
    brandDeals[brand] = {
      slug,
      base_url: baseUrl,
      min_sleep: 600,
      max_sleep: 1200,
      chat_id: CHAT_ID, // Add chat_id to config
      deals: [],
    };
  }
  brandDeals[brand].deals.push({
    deal_id: record['Deal ID'],
    deal_code: record['Code'],
    deal_position: record['Position'],
  });
}

// Generate and save config for each brand
for (const [brand, config] of Object.entries(brandDeals)) {
  const configId = Date.now().toString() + Math.random().toString(36).substring(2, 8); // Unique config ID
  config.config_id = configId;
  const configPath = path.join(CONFIG_DIR, `${configId}.json`);
  fs.writeJsonSync(configPath, config, { spaces: 2 });
  console.log(`Generated config for ${brand} with ID: ${configId}`);
}

console.log('Config generation complete.');