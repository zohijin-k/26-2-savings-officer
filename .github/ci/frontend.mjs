import { readdirSync } from 'node:fs'
import { join, relative } from 'node:path'
import { spawnSync } from 'node:child_process'
const directories = ['tests', 'src/lib', 'src/forms', 'src/pages/officer']
const files = directories.flatMap(directory => {
  try { return readdirSync(directory).filter(file => file.endsWith('.test.ts')).map(file => join(directory, file)) }
  catch (error) { if (error.code === 'ENOENT') return []; throw error }
})
if (!files.length) throw new Error('No Node regression tests found')
const result = spawnSync(process.execPath, ['--test', ...files.sort()], { stdio: 'inherit' })
process.exit(result.status ?? 1)
