import { describe, expect, it } from 'vitest'
import { findPhysicalUtilities } from './rtl'

describe('findPhysicalUtilities', () => {
  it.each([
    'ml-2',
    'mr-4',
    'pl-3',
    'pr-1',
    'ml-auto',
    'pl-[3px]',
    '-ml-2',
    'md:pr-6',
    'hover:ml-1',
    'left-0',
    'right-4',
    '-right-2',
    'rounded-l',
    'rounded-r-lg',
    'rounded-tl-md',
    'rounded-br',
    'border-l',
    'border-r-2',
    'float-left',
    'float-right',
    'text-left',
    'text-right',
    'scroll-ml-2',
    'scroll-pr-4',
  ])('flags %s', (cls) => {
    expect(findPhysicalUtilities(`<div className="flex ${cls} gap-2">`)).toEqual([cls])
  })

  it.each([
    'ms-2',
    'me-auto',
    'ps-[3px]',
    'pe-1',
    'start-0',
    'end-4',
    'rounded-s',
    'rounded-e-lg',
    'rounded-lg',
    'border-s',
    'border-line',
    'text-start',
    'text-end',
    'px-4',
    'mx-auto',
    'inset-x-0',
  ])('allows %s', (cls) => {
    expect(findPhysicalUtilities(`<div className="${cls}">`)).toEqual([])
  })

  it('ignores ordinary prose such as "right-to-left"', () => {
    expect(findPhysicalUtilities('// renders right-to-left in Hebrew')).toEqual([])
  })
})
