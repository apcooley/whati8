/** Core macronutrient keys — always visible in food entry forms. */
export const CORE_NUTRIENTS = ['calories', 'protein_g', 'fat_g', 'carbs_g', 'fiber_g'];

/** Human-readable labels for all tracked nutrients. */
export const NUTRIENT_LABELS: Record<string, string> = {
  calories: 'Calories', protein_g: 'Protein (g)', fat_g: 'Fat (g)',
  saturated_fat_g: 'Sat. Fat (g)', trans_fat_g: 'Trans Fat (g)',
  carbs_g: 'Carbs (g)', fiber_g: 'Fiber (g)', sugars_g: 'Sugars (g)',
  added_sugars_g: 'Added Sugars (g)', cholesterol_mg: 'Cholesterol (mg)',
  sodium_mg: 'Sodium (mg)', vitamin_d_mcg: 'Vitamin D (mcg)',
  calcium_mg: 'Calcium (mg)', iron_mg: 'Iron (mg)', potassium_mg: 'Potassium (mg)',
  vitamin_a_mcg: 'Vitamin A (mcg)', vitamin_c_mg: 'Vitamin C (mg)',
  vitamin_e_mg: 'Vitamin E (mg)', vitamin_k_mcg: 'Vitamin K (mcg)',
  thiamin_mg: 'Thiamin (mg)', riboflavin_mg: 'Riboflavin (mg)',
  niacin_mg: 'Niacin (mg)', vitamin_b6_mg: 'Vitamin B6 (mg)',
  folate_mcg: 'Folate (mcg)', vitamin_b12_mcg: 'Vitamin B12 (mcg)',
  biotin_mcg: 'Biotin (mcg)', pantothenic_acid_mg: 'Pantothenic Acid (mg)',
  phosphorus_mg: 'Phosphorus (mg)', iodine_mcg: 'Iodine (mcg)',
  magnesium_mg: 'Magnesium (mg)', zinc_mg: 'Zinc (mg)',
  selenium_mcg: 'Selenium (mcg)', copper_mg: 'Copper (mg)',
  manganese_mg: 'Manganese (mg)', chromium_mcg: 'Chromium (mcg)',
  molybdenum_mcg: 'Molybdenum (mcg)', chloride_mg: 'Chloride (mg)',
};

/** All optional (non-core) nutrient keys. */
export const ALL_OPTIONAL = Object.keys(NUTRIENT_LABELS).filter(k => !CORE_NUTRIENTS.includes(k));

/** Volume unit conversions to mL. */
export const VOLUME_TO_ML: Record<string, number> = {
  tsp: 4.929,
  tbsp: 14.787,
  'fl oz': 29.5735,
  cup: 236.588,
  pint: 473.176,
  quart: 946.353,
  L: 1000,
  mL: 1,
};

/** Volume unit options for dropdowns. */
export const VOLUME_UNITS = [
  { value: '', label: '-- none --' },
  { value: 'tsp', label: 'tsp' },
  { value: 'tbsp', label: 'tbsp' },
  { value: 'fl oz', label: 'fl oz' },
  { value: 'cup', label: 'cup' },
  { value: 'pint', label: 'pint' },
  { value: 'quart', label: 'quart' },
  { value: 'L', label: 'L' },
  { value: 'mL', label: 'mL' },
];
