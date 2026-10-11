const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// Reveals agent steps one at a time to fake a backend call. Swap for real API calls later.
export const runMockSteps = async (steps: string[], onStep: (shown: string[]) => void, stepMs = 900) => {
  for (let i = 0; i < steps.length; i++) {
    onStep(steps.slice(0, i + 1))
    await wait(stepMs)
  }
}
