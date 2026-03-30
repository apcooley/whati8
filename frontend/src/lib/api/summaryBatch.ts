import { getBatchFoodSummary, type SummaryNutrient, type BatchSummaryRequest } from './foods';

interface PendingRequest {
  food_id: number;
  quantity: number;
  resolve: (value: SummaryNutrient[]) => void;
  reject: (reason: unknown) => void;
}

let pending: PendingRequest[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;
const BATCH_DELAY_MS = 50;

async function flushBatch() {
  const batch = pending.splice(0);
  if (batch.length === 0) return;
  try {
    const items: BatchSummaryRequest[] = batch.map(r => ({
      food_id: r.food_id,
      quantity: r.quantity,
    }));
    const results = await getBatchFoodSummary(items);
    for (const req of batch) {
      const key = `${req.food_id}:${req.quantity}`;
      req.resolve(results[key] || []);
    }
  } catch (err) {
    for (const req of batch) {
      req.reject(err);
    }
  }
}

export function getFoodSummaryBatched(foodId: number, quantity: number): Promise<SummaryNutrient[]> {
  return new Promise((resolve, reject) => {
    pending.push({ food_id: foodId, quantity, resolve, reject });
    if (timer) clearTimeout(timer);
    timer = setTimeout(flushBatch, BATCH_DELAY_MS);
  });
}
