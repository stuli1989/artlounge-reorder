import { useState, useCallback, useEffect } from 'react'
import Joyride, { CallBackProps, STATUS, EVENTS, ACTIONS } from 'react-joyride'
import { useNavigate, useLocation } from 'react-router-dom'
import { TOUR_STEPS, STEP_ROUTE_MAP } from '@/lib/tour-steps'

const TOUR_STORAGE_KEY = 'tourCompleted'

function getRouteForStep(stepIndex: number): string | null {
  for (const mapping of STEP_ROUTE_MAP) {
    if (stepIndex >= mapping.start && stepIndex <= mapping.end) {
      return mapping.route
    }
  }
  return null
}

function waitForTarget(selector: string, timeoutMs = 5000): Promise<Element | null> {
  return new Promise((resolve) => {
    const el = document.querySelector(selector)
    if (el) { resolve(el); return }
    const start = Date.now()
    const poll = () => {
      const el = document.querySelector(selector)
      if (el) { resolve(el); return }
      if (Date.now() - start > timeoutMs) { resolve(null); return }
      requestAnimationFrame(poll)
    }
    requestAnimationFrame(poll)
  })
}

interface GuidedTourProps {
  run: boolean
  onFinish: () => void
}

export default function GuidedTour({ run, onFinish }: GuidedTourProps) {
  const [stepIndex, setStepIndex] = useState(0)
  const [isReady, setIsReady] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (!run || !isReady) return
    const step = TOUR_STEPS[stepIndex]
    if (!step || step.target === 'body') return
    const target = step.target as string
    setIsReady(false)
    waitForTarget(target).then(() => {
      setIsReady(true)
    })
  }, [stepIndex, location.pathname, run])

  const handleCallback = useCallback((data: CallBackProps) => {
    const { action, index, status, type } = data
    if (status === STATUS.FINISHED || status === STATUS.SKIPPED) {
      localStorage.setItem(TOUR_STORAGE_KEY, 'true')
      onFinish()
      return
    }
    if (type === EVENTS.STEP_AFTER) {
      const nextIndex = action === ACTIONS.PREV ? index - 1 : index + 1
      if (nextIndex < 0 || nextIndex >= TOUR_STEPS.length) return
      const currentRoute = getRouteForStep(index)
      const nextRoute = getRouteForStep(nextIndex)
      if (nextRoute && nextRoute !== currentRoute) {
        setIsReady(false)
        navigate(nextRoute)
        setTimeout(() => {
          setStepIndex(nextIndex)
        }, 300)
      } else {
        setStepIndex(nextIndex)
      }
    }
  }, [navigate, onFinish])

  if (!run) return null

  return (
    <Joyride
      steps={TOUR_STEPS}
      stepIndex={stepIndex}
      run={run && isReady}
      continuous
      showSkipButton
      showProgress
      disableOverlayClose
      spotlightClicks={false}
      callback={handleCallback}
      locale={{
        back: 'Back',
        close: 'Close',
        last: 'Finish',
        next: 'Next',
        skip: 'Skip tour',
      }}
      styles={{
        options: {
          primaryColor: '#18181b',
          zIndex: 10000,
        },
        tooltip: {
          borderRadius: '8px',
          fontSize: '14px',
        },
        tooltipTitle: {
          fontSize: '15px',
          fontWeight: 600,
        },
        buttonNext: {
          borderRadius: '6px',
          fontSize: '13px',
          padding: '8px 16px',
        },
        buttonBack: {
          color: '#71717a',
          fontSize: '13px',
        },
        buttonSkip: {
          color: '#a1a1aa',
          fontSize: '12px',
        },
      }}
    />
  )
}

export function isTourCompleted(): boolean {
  return localStorage.getItem(TOUR_STORAGE_KEY) === 'true'
}

export function resetTour(): void {
  localStorage.removeItem(TOUR_STORAGE_KEY)
}
