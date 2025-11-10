import queue
from google.cloud import speech

speech_client = speech.SpeechClient()
LANGUAGE_CODE = "id-ID"

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  

def gcp_streaming_recognize(audio_q: queue.Queue, result_q: queue.Queue):
    """
    Consume PCM16 16k mono chunks from audio_q and push (transcript, is_final) into result_q.
    This function runs in a separate thread.
    """
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=SAMPLE_RATE,
        language_code=LANGUAGE_CODE,
        enable_automatic_punctuation=True,
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config,
        interim_results=True # Receive partial results quickly
    )

    def requests_generator():
        """Generator function that yields audio chunks as GCP requests."""
        while True:
            # Block until a chunk arrives or a sentinel is received
            chunk = audio_q.get()
            if chunk is None:
                print("Recognizer received stop signal (generator stopping)")
                break
            if len(chunk) == 0:
                continue
            yield speech.StreamingRecognizeRequest(audio_content=chunk)
        # The stream is closed when this generator function returns

    print("GCP recognizer starting...")
    # Call the API and pass the generator; GCP handles the input stream
    responses_iterator = speech_client.streaming_recognize(
        config=streaming_config, requests=requests_generator()
    )
    print("GCP recognizer connected to API, processing responses...")

    # Iterate over responses in this same thread
    try:
        for response in responses_iterator:
            # print("Received response", response) # Uncomment for detailed debugging
            if not response.results:
                continue

            result = response.results[0]
            if not result.alternatives:
                continue
                
            transcript = result.alternatives[0].transcript
            is_final = bool(result.is_final)
            
            # Push results immediately to the async loop's queue
            result_q.put((transcript, is_final))
            
            if is_final:
                print(f"Final transcript sent to queue: {transcript}")

    except Exception as e:
        print(f"Error during GCP streaming recognition: {e}")
        # Surface recognizer errors to the sender loop
        result_q.put((f"[recognizer error] {e}", True))
    finally:
        # Signal that we are done processing to the main loop
        result_q.put((None, True)) # Sentinel to stop the forward_results task
        print("GCP Recognizer thread finished.")