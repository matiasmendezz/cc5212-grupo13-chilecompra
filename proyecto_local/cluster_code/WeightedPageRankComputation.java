package cl.uchile.pmd;

import org.apache.giraph.graph.BasicComputation;
import org.apache.giraph.graph.Vertex;
import org.apache.giraph.edge.Edge;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.LongWritable;
import java.io.IOException;

/**
 * WeightedPageRankComputation - CC5212 Procesamiento Masivo de Datos
 * Implementación de PageRank Ponderado para Apache Giraph (Modelo Pregel).
 *
 * Cada vértice distribuye su PageRank a sus vecinos de forma proporcional
 * al peso de la arista (w_uv):
 *   msg(u -> v) = rank(u) * (w_uv / sum_k w_uk)
 *
 * En cada superstep s >= 1:
 *   rank(v) = (1 - d) / N + d * sum_{u in In(v)} msg(u -> v)
 */
public class WeightedPageRankComputation extends BasicComputation<
    LongWritable, DoubleWritable, DoubleWritable, DoubleWritable> {

    public static final int MAX_SUPERSTEPS = 30;
    public static final double DAMPING_FACTOR = 0.85;

    @Override
    public void compute(
            Vertex<LongWritable, DoubleWritable, DoubleWritable> vertex,
            Iterable<DoubleWritable> messages) throws IOException {

        long totalVertices = getTotalNumVertices();

        // 1. En superstep >= 1, agregar los mensajes recibidos y actualizar PageRank
        if (getSuperstep() >= 1) {
            double sum = 0.0;
            for (DoubleWritable message : messages) {
                sum += message.get();
            }
            double newRank = ((1.0 - DAMPING_FACTOR) / totalVertices) + (DAMPING_FACTOR * sum);
            vertex.setValue(new DoubleWritable(newRank));
        }

        // 2. Transmitir PageRank ponderado a los vecinos hasta MAX_SUPERSTEPS
        if (getSuperstep() < MAX_SUPERSTEPS) {
            double totalOutgoingWeight = 0.0;
            for (Edge<LongWritable, DoubleWritable> edge : vertex.getEdges()) {
                totalOutgoingWeight += edge.getValue().get();
            }

            double currentRank = vertex.getValue().get();
            if (totalOutgoingWeight > 0.0) {
                for (Edge<LongWritable, DoubleWritable> edge : vertex.getEdges()) {
                    double edgeWeight = edge.getValue().get();
                    double msgValue = currentRank * (edgeWeight / totalOutgoingWeight);
                    sendMessage(edge.getTargetVertexId(), new DoubleWritable(msgValue));
                }
            }
        } else {
            // Condición de parada de Pregel
            vertex.voteToHalt();
        }
    }
}
