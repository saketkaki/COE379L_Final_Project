import copy
import json
from collections.abc import Iterable
import os
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, TypeAdapter