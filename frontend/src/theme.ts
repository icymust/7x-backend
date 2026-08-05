import { definePreset } from '@primeuix/themes'
import Aura from '@primeuix/themes/aura'

// Palette derived from 7x.ae: black/navy surfaces with the deep blue
// used across their hero gradient (#001ce0 / #000c60).
export const SevenXPreset = definePreset(Aura, {
  semantic: {
    primary: {
      50: '#EAF1FF',
      100: '#D3E3FF',
      200: '#A8C7FF',
      300: '#7CA8FF',
      400: '#4A7DFF',
      500: '#0020F5',
      600: '#001CE0',
      700: '#0016B0',
      800: '#001080',
      900: '#000C60',
      950: '#000625',
    },
    surface: {
      0: '#ffffff',
      50: '#F7F8FA',
      100: '#F0F2F4',
      200: '#E1E4E8',
      300: '#C7CDD4',
      400: '#9AA5B1',
      500: '#6B7684',
      600: '#4C5A6B',
      700: '#364152',
      800: '#1B2333',
      900: '#0F1520',
      950: '#050914',
    },
  },
})

export const BRAND_COLORS = {
  blue: '#001ce0',
  navy: '#050914',
} as const
