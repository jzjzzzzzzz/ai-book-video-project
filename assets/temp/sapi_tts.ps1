param([string]$TextPath,[string]$OutPath)
Add-Type -AssemblyName System.Speech
$s=New-Object System.Speech.Synthesis.SpeechSynthesizer
$v=$s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Culture.Name -eq 'zh-CN'} | Select-Object -First 1
if($v){$s.SelectVoice($v.VoiceInfo.Name)}
$s.Rate=3; $s.Volume=100
$s.SetOutputToWaveFile($OutPath)
$s.Speak([IO.File]::ReadAllText($TextPath,[Text.Encoding]::UTF8))
$s.Dispose()
