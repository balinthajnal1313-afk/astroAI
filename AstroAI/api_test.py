from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5-mini",
    input="Szia! Mondj egy rövid, vicces mondatot magyarul."
)

print(response.output_text) 