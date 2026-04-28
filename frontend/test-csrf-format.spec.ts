import { test } from '@playwright/test'
import { login } from './tests/e2e/setup'

test('Vérifier format localStorage CSRF', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => localStorage.clear())
  
  await login(page)
  await page.waitForTimeout(3000)
  
  const authData = await page.evaluate(() => {
    const auth = localStorage.getItem('marveline-auth')
    return auth ? JSON.parse(auth) : null
  })
  
  const uiData = await page.evaluate(() => {
    const ui = localStorage.getItem('marveline-ui')
    return ui ? JSON.parse(ui) : null
  })
  
  console.log('\n=== AUTHSTORE ===')
  console.log(JSON.stringify(authData, null, 2))
  
  console.log('\n=== UISTORE ===')
  console.log(JSON.stringify(uiData, null, 2))
  
  console.log('\n=== TOKENS ===')
  console.log('accessToken présent:', !!authData?.state?.accessToken || !!authData?.accessToken)
  console.log('csrfToken présent:', !!uiData?.state?.csrfToken || !!uiData?.csrfToken)
  console.log('csrfToken dans state:', uiData?.state?.csrfToken?.substring(0, 20))
  console.log('csrfToken direct:', uiData?.csrfToken?.substring(0, 20))
})
