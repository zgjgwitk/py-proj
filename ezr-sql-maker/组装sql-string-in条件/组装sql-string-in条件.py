import os
import json
import logging
from typing import List, Optional, Dict, Any

# output_format: [sql_in, json_array]

class FormatterConfig:
    def __init__(
        self,
        output_format: str = "sql_in",
        json_chunk_size: Optional[int] = None,
        json_chunk_spacing_lines: int = 5,
        input_file: str = "ezr-sql-maker/组装sql-string-in条件/input.txt",
        output_file: str = "ezr-sql-maker/组装sql-string-in条件/output.txt",
    ):
        self.output_format = output_format
        self.json_chunk_size = json_chunk_size
        self.json_chunk_spacing_lines = json_chunk_spacing_lines
        self.input_file = input_file
        self.output_file = output_file

    @staticmethod
    def load(config_path: str) -> "FormatterConfig":
        if not os.path.exists(config_path):
            return FormatterConfig()
        with open(config_path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
        output_format = str(data.get("output_format", "sql_in")).strip()
        json_chunk_size_raw = data.get("json_chunk_size", None)
        json_chunk_size = None
        if isinstance(json_chunk_size_raw, int):
            if json_chunk_size_raw > 0:
                json_chunk_size = json_chunk_size_raw
        spacing_raw = data.get("json_chunk_spacing_lines", 5)
        spacing_lines = 5
        if isinstance(spacing_raw, int) and spacing_raw > 0:
            spacing_lines = spacing_raw
        input_file = str(data.get("input_file", "ezr-sql-maker/组装sql-string-in条件/input.txt")).strip()
        output_file = str(data.get("output_file", "ezr-sql-maker/组装sql-string-in条件/output.txt")).strip()
        return FormatterConfig(output_format, json_chunk_size, spacing_lines, input_file, output_file)


class SqlStringInAssembler:
    def __init__(self, config: FormatterConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger("SqlStringInAssembler")

    def read_input(self, filename: str) -> List[str]:
        self.logger.info("读取输入文件: %s", filename)
        if not os.path.exists(filename):
            raise FileNotFoundError(f"输入文件 {filename} 不存在")
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()
        items = [line.strip() for line in lines if isinstance(line, str) and line.strip()]
        self.logger.info("读取到有效行数: %d", len(items))
        return items

    def write_output(self, content: str, filename: str) -> None:
        self.logger.info("写入输出文件: %s", filename)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        self.logger.info("输出完成: %s", filename)

    def format_sql_in(self, data_list: List[str]) -> str:
        if not isinstance(data_list, list):
            raise TypeError("输入必须是列表类型")
        safe_items = [("'" + str(item).replace("'", "''") + "'") for item in data_list]
        return ",\n".join(safe_items)

    def _chunk(self, data_list: List[str], size: int) -> List[List[str]]:
        if size <= 0:
            return [data_list]
        chunks: List[List[str]] = []
        start = 0
        total = len(data_list)
        while start < total:
            end = start + size
            chunks.append(data_list[start:end])
            start = end
        return chunks

    def format_json_arrays(self, data_list: List[str], chunk_size: Optional[int]) -> str:
        if chunk_size is None or chunk_size <= 0:
            return json.dumps([str(x) for x in data_list], ensure_ascii=False, indent=2)
        arrays = self._chunk([str(x) for x in data_list], chunk_size)
        serialized = [json.dumps(arr, ensure_ascii=False, indent=2) for arr in arrays]
        sep = "\n" * (self.config.json_chunk_spacing_lines + 1)
        return sep.join(serialized)

    def run(self) -> None:
        mode = self.config.output_format
        if mode not in ("sql_in", "json_array"):
            raise ValueError("output_format 配置只支持 'sql_in' 或 'json_array'")
        items = self.read_input(self.config.input_file)
        if len(items) == 0:
            self.logger.warning("输入为空，无需输出")
            return
        if mode == "sql_in":
            content = self.format_sql_in(items)
        else:
            content = self.format_json_arrays(items, self.config.json_chunk_size)
        self.write_output(content, self.config.output_file)


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("SqlStringInAssembler")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def main():
    logger = _setup_logger()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.json")
    logger.info("载入配置: %s", config_path)
    config = FormatterConfig.load(config_path)
    assembler = SqlStringInAssembler(config, logger)
    assembler.run()


if __name__ == "__main__":
    main()
