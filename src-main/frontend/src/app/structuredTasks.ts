type Item = { id: string; text: string; source_references: string[] }
export type StructuredDefinition = { task_type: 'matching'; prompts: Item[]; options: Item[]; schema_version: string }
  | { task_type: 'sequencing'; items: Item[]; schema_version: string }

export function parsed(answer: string): Record<string, unknown> {
  try { const value: unknown = JSON.parse(answer); return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} } catch { return {} }
}
export const pairsOf = (answer: string): Record<string, string> => {
  const pairs = parsed(answer).pairs
  return pairs && typeof pairs === 'object' && !Array.isArray(pairs) ? Object.fromEntries(Object.entries(pairs).filter((entry): entry is [string, string] => typeof entry[1] === 'string')) : {}
}
export const orderOf = (answer: string): string[] => {
  const order = parsed(answer).order
  return Array.isArray(order) ? order.filter((item): item is string => typeof item === 'string') : []
}

export function validStructured(definition: StructuredDefinition | null | undefined, answer: string): boolean {
  if (!definition) return false
  if (definition.task_type === 'matching') {
    const pairs = pairsOf(answer)
    return Object.keys(pairs).length === definition.prompts.length && new Set(Object.values(pairs)).size === definition.prompts.length && definition.prompts.every(item => definition.options.some(option => option.id === pairs[item.id]))
  }
  const order = orderOf(answer)
  return order.length === definition.items.length && new Set(order).size === order.length && order.every(id => definition.items.some(item => item.id === id))
}

