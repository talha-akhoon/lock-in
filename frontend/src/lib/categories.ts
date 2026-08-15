import {
  BookOpen,
  BriefcaseBusiness,
  Dumbbell,
  Gauge,
  Heart,
  type LucideIcon,
} from 'lucide-react'
import { CATEGORIES, type Category } from './types'

type Meta = {
  label: string
  icon: LucideIcon
  prompt: string
}

export const CATEGORY_META: Record<Category, Meta> = {
  RELIGIOUS: {
    label: 'Religious',
    icon: BookOpen,
    prompt: 'Prayer, scripture, knowledge, character.',
  },
  PHYSICAL: {
    label: 'Physical',
    icon: Dumbbell,
    prompt: 'Strength, weight, endurance, health.',
  },
  CAREER: {
    label: 'Career',
    icon: BriefcaseBusiness,
    prompt: 'Role, skills, compensation, reputation.',
  },
  BUSINESS: {
    label: 'Business',
    icon: Gauge,
    prompt: 'Products shipped, revenue, customers.',
  },
  PERSONAL: {
    label: 'Personal',
    icon: Heart,
    prompt: 'Relationships, finances, habits, hobbies.',
  },
}

export const CATEGORY_ORDER = CATEGORIES

export function categoryLabel(category: Category): string {
  return CATEGORY_META[category]?.label ?? category
}

export const TRACKING_LABELS: Record<string, string> = {
  MILESTONE: 'Done or not done',
  NUMERIC: 'A number moving to a target',
  COUNT: 'A running total',
  MANUAL: 'A percentage you set yourself',
}
