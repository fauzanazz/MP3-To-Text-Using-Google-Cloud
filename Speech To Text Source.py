import os
from retry import retry
from pydub import AudioSegment
from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core.client_options import ClientOptions
from tqdm import tqdm


def mp3toflac(filepath):
    audio = AudioSegment.from_mp3(filepath)
    audio.export(flac_filepath, format='flac')

def upload_blob(content_type=None):
    bucket_name = "your_bucket_name"
    # The path to your file to upload
    # flac_filepath = "local/path/to/file"
    # The ID of your GCS object
    destination_blob_name = flac_filepath
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    with open(flac_filepath, "rb") as in_file:
        total_bytes = os.fstat(in_file.fileno()).st_size
        with tqdm.wrapattr(in_file, "read", total=total_bytes, miniters=1, desc="upload to %s" % bucket_name) as file_obj:
            blob.upload_from_file(
                file_obj,
                content_type=content_type,
                size=total_bytes,
            )
    print(
        f"File {flac_filepath} uploaded to {bucket_name}."
    )
    return blob
    
def transcribe_chirp(project_id: str,gcs_uri: str,) -> cloud_speech.BatchRecognizeResults:
    """Transcribe an audio file using Chirp."""
    # Instantiates a client
    client = SpeechClient(
        client_options=ClientOptions(
            api_endpoint="asia-southeast1-speech.googleapis.com",
        )
    )

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
        language_codes=["id-ID"],
        model="chirp",
    )
    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=gcs_uri)
    
    request = cloud_speech.BatchRecognizeRequest(
        recognizer=f"projects/{project_id}/locations/asia-southeast1/recognizers/_",
        config=config,
        files=[file_metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            inline_response_config=cloud_speech.InlineOutputConfig(),
        ),
    )
    # Add the retry decorator to the long_running_recognize function
    @retry(tries=5, delay=10, backoff=2)
    def long_running_recognize_with_retry(request):
        operation = client.batch_recognize(request=request,timeout=120)
        return operation.result()

    try:
        output_file = flac_filepath.replace(".flac", ".txt")
        with open(output_file, "w") as file:
            response = long_running_recognize_with_retry(request)
            if gcs_uri in response.results:
                for result in response.results[gcs_uri].transcript.results:
                    if len(result.alternatives) > 0:
                        transcript_text = result.alternatives[0].transcript
                        file.write(f"{transcript_text}\n")
                        print(f"Transcript: {transcript_text}")
                    else:
                        print("No transcription alternative found.")
            else:
                print("No results found for the specified gcs_uri.")
    except Exception as e:
        print(f"Error: {e}")

def pause_and_resume():
    print("Press Enter to resume...")
    input()  # The program will pause and wait for the user to press Enter
    print("Resuming after Enter")
    
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "Credential.json"


print("Pastikan file mp3 sudah satu folder dengan program ini!\n")
filepath = input("Masukkan nama file: ")

#MP3 to Flac
flac_filepath = filepath.replace(".mp3", ".flac")
mp3toflac(filepath)

# Uploading mp3 to cloud storage
upload = input("Upload? y/n ")
if upload== 'y':
    upload_blob(flac_filepath)
else:
    print("Not uploading")
    
projectID = 'Your-Project-ID'
gcs_uri = f"gs://Your-Bucket-Name/{flac_filepath}"
transcribe_chirp(project_id=projectID, gcs_uri=gcs_uri)
pause_and_resume()