import { useId } from 'react'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './RadioGroup.module.css'

export interface RadioOption {
  value: string
  label: ReactNode
  help?: ReactNode
}

export interface RadioGroupProps {
  legend: string
  name: string
  options: RadioOption[]
  value: string | null
  onChange: (value: string) => void
  className?: string
}

export function RadioGroup({ legend, name, options, value, onChange, className }: RadioGroupProps) {
  const id = useId()
  return (
    <fieldset className={cx(styles.group, className)}>
      <legend className={styles.legend}>{legend}</legend>
      {options.map((option, index) => (
        <label key={option.value} className={styles.option} htmlFor={`${id}-${index}`}>
          <input
            id={`${id}-${index}`}
            className={styles.input}
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          <span className={styles.text}>
            <span className={styles.label}>{option.label}</span>
            {option.help ? <span className={styles.help}>{option.help}</span> : null}
          </span>
        </label>
      ))}
    </fieldset>
  )
}
