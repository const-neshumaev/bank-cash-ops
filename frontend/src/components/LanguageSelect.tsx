import { Button, Menu } from '@mantine/core'
import { IconChevronDown, IconLanguage } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'

import * as authApi from '../api/auth'
import { useAuth } from '../auth/AuthContext'
import { useLanguage } from '../i18n/LanguageContext'

/** Menu that switches the interface language among the bank's offered languages. */
export function LanguageSelect() {
  const { language, languages, changeLanguage } = useLanguage()
  const { user, refreshUser } = useAuth()
  const { t } = useTranslation()

  if (languages.length < 2) {
    return null
  }

  const name = (code: string) =>
    t(`language.names.${code}`, { defaultValue: code.toUpperCase() })

  const handleChange = (code: string) => {
    changeLanguage(code)
    // Persist the per-user choice on the server when signed in.
    if (user) {
      void authApi
        .updateMe({ language: code })
        .then(() => refreshUser())
        .catch(() => undefined)
    }
  }

  return (
    <Menu withinPortal>
      <Menu.Target>
        <Button
          variant="subtle"
          size="compact-md"
          leftSection={<IconLanguage size={16} />}
          rightSection={<IconChevronDown size={14} />}
        >
          {name(language)}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {languages.map((code) => (
          <Menu.Item key={code} onClick={() => handleChange(code)}>
            {name(code)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  )
}
