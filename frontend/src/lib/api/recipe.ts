import { apiRequest } from './client';

export interface RecipeIngredient {
  id: number;
  food_id: number;
  food_name: string;
  quantity: number;
  unit: string;
  portion_description: string;
}

export interface PerServingNutrition {
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  weight_g: number;
}

export interface Recipe {
  id: number;
  name: string;
  servings: number;
  serving_unit: string;
  current_version: number;
  food_id: number;
  ingredients: RecipeIngredient[];
  per_serving: PerServingNutrition;
}

export interface CreateRecipePayload {
  name: string;
  servings: number;
  serving_unit: string;
  ingredients: Array<{
    food_id: number;
    quantity: number;
    unit: string;
    portion_description: string;
  }>;
}

export async function createRecipe(data: CreateRecipePayload): Promise<Recipe> {
  return apiRequest<Recipe>('/recipes/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function listRecipes(): Promise<Recipe[]> {
  return apiRequest<Recipe[]>('/recipes/');
}

export async function getRecipe(id: number): Promise<Recipe> {
  return apiRequest<Recipe>(`/recipes/${id}`);
}

export interface UpdateRecipePayload {
  name?: string;
  servings?: number;
  serving_unit?: string;
}

export async function updateRecipe(id: number, data: UpdateRecipePayload): Promise<Recipe> {
  return apiRequest<Recipe>(`/recipes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export interface AddIngredientPayload {
  food_id: number;
  quantity: number;
  unit: string;
  portion_description: string;
}

export async function addIngredient(recipeId: number, data: AddIngredientPayload): Promise<any> {
  return apiRequest<any>(`/recipes/${recipeId}/ingredients`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function removeIngredient(recipeId: number, ingredientId: number): Promise<void> {
  return apiRequest<void>(`/recipes/${recipeId}/ingredients/${ingredientId}`, {
    method: 'DELETE',
  });
}

export async function canAddFood(recipeId: number, foodId: number): Promise<{allowed: boolean}> {
  return apiRequest<{allowed: boolean}>(`/recipes/${recipeId}/can-add/${foodId}`);
}

export async function deleteRecipe(id: number): Promise<void> {
  return apiRequest<void>(`/recipes/${id}`, {
    method: 'DELETE',
  });
}
