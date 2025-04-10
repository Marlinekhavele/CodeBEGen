'use client'
import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useState,
} from 'react'

type Theme = 'light' | 'dark' | null

interface ThemeContextType {
  theme: Theme
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(null)

  useLayoutEffect(() => {
    const storedTheme = localStorage.getItem('theme') as 'light' | 'dark'
    if (storedTheme) {
      document.documentElement.classList.toggle('dark', storedTheme === 'dark')
      setTheme(storedTheme)
    } else {
      setTheme('dark')
    }
  }, [])

  useEffect(() => {
    if (theme) {
      document.documentElement.classList.toggle('dark', theme === 'dark')
      localStorage.setItem('theme', theme)
    }
  }, [theme])

  const toggleTheme = () => {
    setTheme((prevTheme) => (prevTheme === 'dark' ? 'light' : 'dark'))
  }

  if (theme === null) {
    return null
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
