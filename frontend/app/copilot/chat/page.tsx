import { redirect } from 'next/navigation'

// L'ancienne page chat a été fusionnée dans /copilot (onglets Assistant / Express).
export default function CopilotChatRedirect() {
  redirect('/copilot')
}
