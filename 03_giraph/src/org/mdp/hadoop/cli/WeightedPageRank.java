package org.mdp.hadoop.cli;

import java.io.IOException;

import org.apache.giraph.edge.Edge;
import org.apache.giraph.graph.BasicComputation;
import org.apache.giraph.graph.Vertex;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.IntWritable;
import org.apache.hadoop.io.Text;

/**
 * PageRank ponderado (Grupo 13). Es el PageRank del Lab 8 con un solo cambio:
 * cada vecino recibe D * rank * peso / (suma de pesos de las aristas de salida).
 * Un vertice cuyas aristas suman peso 0 se trata como dangling.
 * Usa los mismos aggregators que PageRank (PageRankAgg).
 */
public class WeightedPageRank extends BasicComputation<Text, DoubleWritable, DoubleWritable, DoubleWritable> {

    public static final int ITERS = PageRank.ITERS;
    public static final double D = PageRank.D;

    @Override
    public void compute(Vertex<Text, DoubleWritable, DoubleWritable> vertex,
                        Iterable<DoubleWritable> messages) throws IOException {
        if (getSuperstep() == 0) {
            // Se activan todos los vertices, incluidos los que no tienen aristas de salida
            sendMessageToAllEdges(vertex, new DoubleWritable(0));
        } else if (getSuperstep() == 1) {
            // Se cuentan los vertices
            aggregate(PageRank.NUM_V_NAME, PageRank.ONE);
        } else {
            int numVertices = ((IntWritable) getAggregatedValue(PageRank.NUM_V_NAME)).get();
            double currentRank = 0;

            if (getSuperstep() == 2) {
                // Rank inicial: 1 / numero de vertices
                currentRank = 1.0 / numVertices;
            } else {
                // Se suman los mensajes recibidos y la parte del salto aleatorio
                for (DoubleWritable message : messages) {
                    currentRank += message.get();
                }
                currentRank += ((DoubleWritable) getAggregatedValue(PageRank.RJ_AGG_NAME)).get() / numVertices;
                vertex.setValue(new DoubleWritable(currentRank));
            }

            if (getSuperstep() == ITERS + 2) {
                vertex.voteToHalt();
            } else {
                // Suma de los pesos de las aristas de salida
                double sumaPesos = 0;
                for (Edge<Text, DoubleWritable> edge : vertex.getEdges()) {
                    sumaPesos += edge.getValue().get();
                }
                if (sumaPesos > 0) {
                    // Cada vecino recibe una parte de D * rank proporcional al peso de su arista
                    for (Edge<Text, DoubleWritable> edge : vertex.getEdges()) {
                        double parte = D * currentRank * edge.getValue().get() / sumaPesos;
                        sendMessage(edge.getTargetVertexId(), new DoubleWritable(parte));
                    }
                    // El resto (1 - D) va al salto aleatorio
                    aggregate(PageRank.RJ_AGG_NAME, new DoubleWritable((1 - D) * currentRank));
                } else {
                    // Sin aristas (o con peso total 0): todo el rank va al salto aleatorio
                    aggregate(PageRank.RJ_AGG_NAME, new DoubleWritable(currentRank));
                }
            }
        }
    }
}
