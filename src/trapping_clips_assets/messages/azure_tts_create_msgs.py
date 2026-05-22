import azure.cognitiveservices.speech as speechsdk
# install this package with: pip install azure-identity
from azure.identity import DefaultAzureCredential

# Replace with your own region identifier from here: https://aka.ms/speech/sdkregion

# Replace with your own region and resource ID
service_region = "Replace with your own region"
# Find resource_id in Azure Portal → Speech resource → Properties → Resource ID
resource_id = "Replace with your own resource ID"

credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default")
# subscription value is overridden by authorization_token below
speech_config = speechsdk.SpeechConfig(subscription="unused", region=service_region)
speech_config.authorization_token = "aad#" + resource_id + "#" + token.token

def create_wav(ans ,output):
    # Creates an audio configuration that points to an audio file.
    # Replace with your own audio filename.
    audio_filename = output
    audio_output = speechsdk.audio.AudioOutputConfig(filename=audio_filename)

    # Creates a synthesizer with the given settings
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_output)

    # Synthesizes the text to speech.
    # Replace with your own text.

    # speak_ssml_async
    tts = f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US"> <voice  name="en-US-AriaNeural"> <express-as style="empathetic"><s>This is an interruption.</s> </express-as><s>Please select the score "{ans}" <break time="100ms" /> to confirm your attention now.</s></voice> </speak>'
    result = speech_synthesizer.speak_ssml_async(tts).get()

    # Checks result.
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized to [{}]".format(audio_filename))
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            if cancellation_details.error_details:
                print("Error details: {}".format(cancellation_details.error_details))
        print("Did you update the subscription info?")


if __name__ == '__main__':
    scores = [1, 2, 3, 4, 5]
    output_name = "p835_score_{}_short.wav"
    for score in scores:
        create_wav(score, output_name.format(score))


