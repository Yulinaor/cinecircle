import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// The default 1 s findBy*/waitFor timeout is too tight for the first test of a file when the
// whole suite runs in parallel on a busy machine.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})
