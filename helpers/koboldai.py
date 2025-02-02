import logging
from typing import Any, Dict, List, Optional

import requests
import asyncio
import aiohttp

import random
import string

from langchain.callbacks.manager import  (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain.llms.base import LLM

logger = logging.getLogger(__name__)

def clean_url(url: str) -> str:
    """Remove trailing slash and /api from url if present."""
    if url.endswith("/api"):
        return url[:-4]
    elif url.endswith("/"):
        return url[:-1]
    else:
        return url


class KoboldApiLLM(LLM):
    """Kobold API language model.

    It includes several fields that can be used to control the text generation process.

    To use this class, instantiate it with the required parameters and call it with a
    prompt to generate text. For example:

        kobold = KoboldApiLLM(endpoint="http://localhost:5000")
        result = kobold("Write a story about a dragon.")

    This will send a POST request to the Kobold API with the provided prompt and
    generate text.
    """

    endpoint: str
    """The API endpoint to use for generating text."""

    use_story: Optional[bool] = False
    """ Whether or not to use the story from the KoboldAI GUI when generating text. """

    use_authors_note: Optional[bool] = False
    """Whether to use the author's note from the KoboldAI GUI when generating text.
    
    This has no effect unless use_story is also enabled.
    """

    use_world_info: Optional[bool] = False
    """Whether to use the world info from the KoboldAI GUI when generating text."""

    use_memory: Optional[bool] = False
    """Whether to use the memory from the KoboldAI GUI when generating text."""

    max_context_length: Optional[int] = 1600
    """Maximum number of tokens to send to the model.
    
    minimum: 1
    """

    max_length: Optional[int] = 80
    """Number of tokens to generate.
    
    maximum: 512
    minimum: 1
    """

    rep_pen: Optional[float] = 1.12
    """Base repetition penalty value.
    
    minimum: 1
    """

    rep_pen_range: Optional[int] = 1024
    """Repetition penalty range.
    
    minimum: 0
    """

    rep_pen_slope: Optional[float] = 0.9
    """Repetition penalty slope.
    
    minimum: 0
    """

    temperature: Optional[float] = 0.6
    """Temperature value.
    
    exclusiveMinimum: 0
    """

    tfs: Optional[float] = 0.9
    """Tail free sampling value.
    
    maximum: 1
    minimum: 0
    """

    top_a: Optional[float] = 0.9
    """Top-a sampling value.
    
    minimum: 0
    """

    top_p: Optional[float] = 0.95
    """Top-p sampling value.
    
    maximum: 1
    minimum: 0
    """

    top_k: Optional[int] = 0
    """Top-k sampling value.
    
    minimum: 0
    """

    typical: Optional[float] = 0.5
    """Typical sampling value.
    
    maximum: 1
    minimum: 0
    """

    # To store genkeys for each generation
    genkeys = {}
    is_koboldcpp = False

    @property
    def _llm_type(self) -> str:
        return "koboldai"

    # Define a helper method to generate the data dict
    def _get_parameters(
        self,
        prompt: str,
        stop: Optional[List[str]] = None) -> Dict[str, Any]:
        """Get the parameters to send to the API."""
        data: Dict[str, Any] = {
            "prompt": prompt,
            "use_story": self.use_story,
            "use_authors_note": self.use_authors_note,
            "use_world_info": self.use_world_info,
            "use_memory": self.use_memory,
            "max_context_length": self.max_context_length,
            "max_length": self.max_length,
            "rep_pen": self.rep_pen,
            "rep_pen_range": self.rep_pen_range,
            "rep_pen_slope": self.rep_pen_slope,
            "temperature": self.temperature,
            "tfs": self.tfs,
            "top_a": self.top_a,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "typical": self.typical,
        }

        if stop:
            data["stop_sequence"] = stop

        return data

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the API and return the output.

        Args:
            prompt: The prompt to use for generation.
            stop: A list of strings to stop generation when encountered.

        Returns:
            The generated text.

        Example:
            .. code-block:: python

                from langchain.llms import KoboldApiLLM

                llm = KoboldApiLLM(endpoint="http://localhost:5000")
                llm("Write a story about dragons.")
        """
        data = self._get_parameters(prompt, stop)

        response = requests.post(
            f"{clean_url(self.endpoint)}/api/v1/generate", json=data
        )

        response.raise_for_status()
        json_response = response.json()

        if (
            "results" in json_response
            and len(json_response["results"]) > 0
            and "text" in json_response["results"][0]
        ):
            text = json_response["results"][0]["text"].strip()

            if stop is not None:
                for sequence in stop:
                    if text.endswith(sequence):
                        text = text[: -len(sequence)].rstrip()

            return text
        else:
            raise ValueError(
                f"Unexpected response format from Kobold API:  {json_response}"
            )
    
    # New function to call KoboldAI API asynchronously
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        channel_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Call the API and return the output.

        Args:
            prompt: The prompt to use for generation.
            stop: A list of strings to stop generation when encountered.

        Returns:
            The generated text.

        Example:
            .. code-block:: python

                from langchain.llms import KoboldApiLLM

                llm = KoboldApiLLM(endpoint="http://localhost:5000")
                llm("Write a story about dragons.")
        """
        if self.is_koboldcpp:
            # Generate a random 10 character genkey
            genkey = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
            print(f"genkey: {genkey}")

            # Store genkeys to dict mapped to channel ID
            self.genkeys[channel_id] = genkey
            data = self._get_parameters(prompt, stop)
            data["genkey"] = genkey

        else:
            # Normal for KoboldAI, genkey is not required
            data = self._get_parameters(prompt, stop)

         # Use aiohttp to call KoboldAI API asynchronously to prevent blocking
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{clean_url(self.endpoint)}/api/v1/generate", json=data) as response:

                response.raise_for_status()
                json_response = await response.json()

                if (
                    "results" in json_response
                    and len(json_response["results"]) > 0
                    and "text" in json_response["results"][0]
                ):
                    text = json_response["results"][0]["text"].strip()

                    if stop is not None:
                        for sequence in stop:
                            if text.endswith(sequence):
                                text = text[: -len(sequence)].rstrip()

                    return text
                else:
                    raise ValueError(
                        f"Unexpected response format from Kobold API:  {json_response}"
                    )

    def check_version(self) -> float:
        """Check the version of the koboldcpp API. To distinguish between KoboldAI and koboldcpp"""
        try:
            response = requests.get(f"{clean_url(self.endpoint)}/api/extra/version")
            response.raise_for_status()
            json_response = response.json()
            self.is_koboldcpp = True
            print("The endpoint is running koboldcpp instead of KoboldAI. If you use multiple channel IDs, please pass '--multiuser' to koboldcpp.")
            return float(json_response["version"])
        except:
            # Try fetching KoboldAI version
            try:
                response = requests.get(f"{clean_url(self.endpoint)}/api/v1/version")
                response.raise_for_status()
                json_response = response.json()
                self.is_koboldcpp = False
                print("The endpoint is running KoboldAI instead of koboldcpp.")
                return 0.0
            except:
                raise ValueError("The endpoint is not running KoboldAI or koboldcpp.")


    async def _stop(self, channel_id):
        """Send abort request to stop ongoing AI generation.
        This only applies to koboldcpp. Official KoboldAI API does not support this.
        """

        # Check genkey before cancelling
        if channel_id in self.genkeys:
            genkey = self.genkeys[channel_id]

            json = {"genkey": genkey}
        
        try:
            response = requests.post(f"{clean_url(self.endpoint)}/api/extra/abort", json=json)
            if response.status_code == 200 and response.json()["success"] == True:
                print(f"Successfully aborted AI generation for channel ID of {channel_id}, with genkey: {genkey}")
            else:
                print("Error aborting AI generation.")

        except Exception as e:
            print(f"Error aborting AI generation: {e}")