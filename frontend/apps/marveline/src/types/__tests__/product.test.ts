/**
 * Tests unitaires pour les fonctions de types/product.ts
 * Vérifie la dérivation du statut stock, couleurs et labels
 */
import { describe, it, expect } from 'vitest'
import {
  getStockStatus,
  getStockStatusColor,
  getStockStatusLabel,
  getStockBarColor,
} from '../product'

const mkProduct = (available: number, total: number) => ({
  available_quantity: available,
  stock_quantity: total,
})

describe('getStockStatus', () => {
  it('retourne "out_of_stock" quand available_quantity = 0', () => {
    expect(getStockStatus(mkProduct(0, 10))).toBe('out_of_stock')
  })

  it('retourne "in_stock" quand available > 20% du stock', () => {
    expect(getStockStatus(mkProduct(8, 10))).toBe('in_stock')
    expect(getStockStatus(mkProduct(10, 10))).toBe('in_stock')
  })

  it('retourne "low_stock" quand available <= 20% du stock (min 3)', () => {
    // 10 * 20% = 2 → min 3 → seuil = 3
    expect(getStockStatus(mkProduct(3, 10))).toBe('low_stock')
    expect(getStockStatus(mkProduct(2, 10))).toBe('low_stock')
    expect(getStockStatus(mkProduct(1, 10))).toBe('low_stock')
  })

  it('applique seuil minimum de 3 pour les petits stocks', () => {
    // stock=5 → 20%=1 < 3 → seuil=3 → available=2 = low_stock
    expect(getStockStatus(mkProduct(2, 5))).toBe('low_stock')
    // available=4 > 3 = in_stock
    expect(getStockStatus(mkProduct(4, 5))).toBe('in_stock')
  })

  it('retourne "out_of_stock" pour stock total = 0', () => {
    expect(getStockStatus(mkProduct(0, 0))).toBe('out_of_stock')
  })
})

describe('getStockStatusColor', () => {
  it('retourne text-green-500 pour in_stock', () => {
    expect(getStockStatusColor(mkProduct(10, 10))).toBe('text-green-500')
  })

  it('retourne text-yellow-500 pour low_stock', () => {
    expect(getStockStatusColor(mkProduct(2, 10))).toBe('text-yellow-500')
  })

  it('retourne text-red-500 pour out_of_stock', () => {
    expect(getStockStatusColor(mkProduct(0, 10))).toBe('text-red-500')
  })
})

describe('getStockStatusLabel', () => {
  it('retourne "En stock" pour in_stock', () => {
    expect(getStockStatusLabel(mkProduct(10, 10))).toBe('En stock')
  })

  it('retourne "Stock faible" pour low_stock', () => {
    expect(getStockStatusLabel(mkProduct(2, 10))).toBe('Stock faible')
  })

  it('retourne "Rupture" pour out_of_stock', () => {
    expect(getStockStatusLabel(mkProduct(0, 10))).toBe('Rupture')
  })
})

describe('getStockBarColor', () => {
  it('retourne bg-green-500 pour in_stock', () => {
    expect(getStockBarColor(mkProduct(10, 10))).toBe('bg-green-500')
  })

  it('retourne bg-yellow-500 pour low_stock', () => {
    expect(getStockBarColor(mkProduct(2, 10))).toBe('bg-yellow-500')
  })

  it('retourne bg-red-500 pour out_of_stock', () => {
    expect(getStockBarColor(mkProduct(0, 10))).toBe('bg-red-500')
  })
})
